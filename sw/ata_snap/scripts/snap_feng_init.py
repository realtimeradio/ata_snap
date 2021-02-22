#! /usr/bin/env python
import argparse
import time
import yaml
import logging
import sys
import socket
import casperfpga
import struct

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
parser.add_argument('-m', dest='mansync', action='store_true', default=False,
                    help ='Use this flag to issue an internal sync rather than using a PPS')
parser.add_argument('-t', dest='tvg', action='store_true', default=False,
                    help ='Use this flag to switch to post-fft test vector outputs')
parser.add_argument('-i', dest='feng_id', type=int,
                    default=0, help='F-engine ID to write to this SNAP\'s output packets')
parser.add_argument('-p', dest='dest_port', type=int,
                    default=None, help='10GBe destination port')
parser.add_argument('--skipprog', dest='skipprog', action='store_true', default=False,
                    help='Skip programming .fpg file')
parser.add_argument('--usetapcp', dest='usetapcp', action='store_true', default=False,
                    help='Use Tapcp protocol to connect to the SNAP')
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
config['dest_port'] = args.dest_port or config['dest_port']

if args.usetapcp:
    transport = casperfpga.TapcpTransport
else:
    transport = casperfpga.KatcpTransport

logger.info("Connecting to %s" % args.host)
feng = ata_snap_fengine.AtaSnapFengine(args.host,
        transport=transport,
        feng_id=args.feng_id)

if not args.skipprog:
    logger.info("Programming %s with %s" % (args.host, args.fpgfile))
    feng.program(args.fpgfile)
else:
    logger.info("Skipping programming because the --skipprog flag was used")
    # If we're not programming we need to load the FPG information
    feng.fpga.get_system_information(args.fpgfile)

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
    print ("Configuring ip: %s with mac: %x" %(ip, mac))
    for ethn, eth in enumerate(feng.fpga.gbes):
        eth.set_single_arp_entry(ip, mac)

voltage_config = config.get('voltage_output', None)
n_interfaces = voltage_config.get('n_interfaces', feng.n_interfaces)
for i in range(n_interfaces):
    ip = config["interfaces"][feng.fpga.host][i]
    mac = config["arp"][ip]
    port = 10000
    eth = feng.fpga.gbes['eth%i_core' %i]
    eth.configure_core(mac, ip, port)

if args.eth_spec:
    feng.spec_set_destination(config['spectrometer_dest'])

if voltage_config is not None:
    n_chans = voltage_config['n_chans']
    start_chan = voltage_config['start_chan']
    dests = voltage_config['dests']
    logger.info('Voltage output sending channels %d to %d' % (start_chan, start_chan+n_chans-1))
    logger.info('Destination IPs: %s' %dests)
    logger.info('Using %d interfaces' % n_interfaces)
    feng.select_output_channels(start_chan, n_chans, dests, n_interfaces=n_interfaces)

feng.eth_set_dest_port(config['dest_port'])

if args.eth_spec:
    feng.eth_set_mode('spectra')
    feng.fpga.write_int('corr_feng_id', args.feng_id)
elif args.eth_volt:
    feng.eth_set_mode('voltage')

if args.sync:
    if not args.mansync:
        feng.sync_wait_for_pps()
    feng.sync_arm(manual_trigger=args.mansync)

# Reset ethernet cores prior to enabling
feng.eth_reset()
if args.eth_spec or args.eth_volt:
    logger.info('Enabling Ethernet output')
    feng.eth_enable_output(True)
else:
    logger.info('Not enabling Ethernet output, since neither voltage or spectrometer 10GbE output flags were set.')

logger.info("Initialization complete!")
