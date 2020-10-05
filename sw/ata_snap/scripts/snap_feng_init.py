#! /usr/bin/env python
import argparse
import time
import yaml
import logging
import sys
import socket

from ata_snap import ata_snap_fengine

parser = argparse.ArgumentParser(description='Program and initialize a SNAP ADC5G spectrometer',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('host', type=str,
                    help = 'Hostname / IP of SNAP')
parser.add_argument('fpgfile', type=str, 
                    help = '.fpgfile to program')
parser.add_argument('configfile', type=str,
                    help ='Configuration file')
parser.add_argument('-s', dest='sync', action='store_true', default=False,
                    help ='Use this flag to re-arm the design\'s sync logic')
parser.add_argument('-t', dest='tvg', action='store_true', default=False,
                    help ='Use this flag to switch to post-fft test vector outputs')
parser.add_argument('--eth_spec', dest='eth_spec', action='store_true', default=False,
                    help ='Use this flag to switch on Ethernet transmission of the spectrometer')
parser.add_argument('--eth_volt', dest='eth_volt', action='store_true', default=False,
                    help ='Use this flag to switch on Ethernet transmission of F-engine data')
parser.add_argument('-a', dest='acclen', type=int, default=None,
                    help ='Number of spectra to accumulate per spectrometer dump. Default: get from config file')
parser.add_argument('--specdest', dest='specdest', type=str, default=None,
        help ='Destination IP address to which spectra should be sent. Default: get from config file')

args = parser.parse_args()

logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

assert not (args.eth_spec and args.eth_volt), "Can't use both --eth_spec and --eth_volt options!"

# Load configuration file and override parameters with
# user flags
with open(args.configfile, 'r') as fh:
    config = yaml.load(fh, Loader=yaml.SafeLoader)

config['acclen'] = args.acclen or config['acclen']
config['spectrometer_dest'] = args.specdest or config['spectrometer_dest']

logger.info("Connecting to %s" % args.host)
feng = ata_snap_fengine.AtaSnapFengine(args.host)
feng.logger.addHandler(handler)
logger.info("Programming %s with %s" % (args.host, args.fpgfile))
feng.program(args.fpgfile)

# Disable ethernet output before doing anything
feng.eth_enable_output(False)

feng.set_accumulation_length(config['acclen'])

# Use the same coefficients for both polarizations
feng.eq_load_coeffs(0, config['coeffs'])
feng.eq_load_coeffs(1, config['coeffs'])

feng.eq_load_test_vectors(0, list(range(feng.n_chans_f)))
feng.eq_load_test_vectors(1, list(range(feng.n_chans_f)))
feng.eq_test_vector_mode(enable=args.tvg)
feng.spec_test_vector_mode(enable=args.tvg)

# Configure arp table
for ip, mac in config['arp'].items():
    feng.fpga.gbes.eth_core.set_single_arp_entry(ip, mac)
# Configure 10G IP
ip_str = socket.gethostbyname(feng.fpga.host)
mac = feng.fpga.gbes.eth_core.get_gbe_core_details()['mac'].mac_int
feng.fpga.gbes.eth_core.setup(mac, ip_str, 10000, '10.10.10.10', '255.255.255.0')
feng.fpga.gbes.eth_core.configure_core()

if args.specdest is not None:
    feng.spec_set_destination(config['spectrometer_dest'])

voltage_config = config.get('voltage_output', None)
if voltage_config is not None:
    n_chans = voltage_config['n_chans']
    start_chan = voltage_config['start_chan']
    dests = voltage_config['dests']
    logger.info('Voltage output sending channels %d to %d' % (start_chan, start_chan+n_chans-1))
    logger.info('Destination IPs: %s' %dests)
    feng.select_output_channels(start_chan, n_chans, dests)

feng.eth_set_dest_port(config['dest_port'])

if args.eth_spec:
    feng.eth_set_mode('spectra')
elif args.eth_volt:
    feng.eth_set_mode('voltage')

if args.eth_spec or args.eth_volt:
    logger.info('Enabling Ethernet output')
    feng.eth_enable_output(True)
else:
    logger.info('Not enabling Ethernet output, since neither voltage or spectrometer 10GbE output flags were set.')

if args.sync:
    feng.sync_wait_for_pps()
    feng.sync_arm()

logger.info("Initialization complete!")
