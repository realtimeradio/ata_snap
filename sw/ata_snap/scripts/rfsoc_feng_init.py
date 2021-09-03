#! /usr/bin/env python
import time
import yaml
import logging
import sys
import socket
import casperfpga
import struct

from ata_snap import ata_rfsoc_fengine

def run(host, fpgfile, configfile,
        sync=False,
        mansync=False,
        tvg=False,
        feng_ids=[0,1,2,3],
        pipeline_ids=[0,1,2,3],
        dest_port=None,
        skipprog=False,
        eth_spec=False,
        noblank=False,
        eth_volt=False,
        acclen=250000,
        testmode=False,
        specdest=None,
        dests=None
        ):
    logger = logging.getLogger(__file__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    assert not (eth_spec and eth_volt), "Can't use both --eth_spec and --eth_volt options!"

    # Load configuration file and override parameters with
    # user flags
    with open(configfile, 'r') as fh:
        config = yaml.load(fh, Loader=yaml.SafeLoader)

    config['acclen'] = acclen or config['acclen']
    config['dest_port'] = dest_port or config['dest_port']
    if isinstance(config['dest_port'], str):
        config['dest_port'] = list(map(int, config['dest_port'].split(',')))
    config['voltage_output']['dests'] = dests or config['voltage_output']['dests']

    logger.info("Connecting to %s" % host)
    fengs = []
    assert len(feng_ids) <= 8, "At most 8 F-Engine IDs supported"
    assert len(pipeline_ids) == len(feng_ids), "pipeline_ids and feng_ids should have the same length"
    cfpga = casperfpga.CasperFpga(host, transport=casperfpga.KatcpTransport)
    logger.info("Connected")
    for pipeline_id, feng_id in zip(pipeline_ids, feng_ids):
        fengs += [ata_rfsoc_fengine.AtaRfsocFengine(cfpga, feng_id=feng_id, pipeline_id=pipeline_id)]

    if not skipprog:
        logger.info("Programming %s with %s" % (host, fpgfile))
        fengs[0].program(fpgfile)
    else:
        logger.info("Skipping programming because the --skipprog flag was used")
        # If we're not programming we need to load the FPG information
        fengs[0].fpga.get_system_information(fpgfile)

    logger.info("Enabling ADC")
    fengs[0].fpga.write_int('adc_rstn', 1)

    logger.info("Estimating FPGA clock")
    clk_rate_mhz = fengs[0].fpga.estimate_fpga_clock()
    logger.info("Clock rate: %.1f MHz" % clk_rate_mhz)

    # Firmware doesn't respect FFT shift, so don't pretend it does!

    #fft_shift = 0xff
    #if not testmode:
    #    logger.info("Setting FFT shift to 0x%x" % fft_shift)
    #    for feng in fengs:
    #        feng.fpga.write_int("pfb_fft_shift", fft_shift)

    # Disable ethernet output before doing anything
    #fengs[0].eth_enable_output(False)

    fengs[0].set_accumulation_length(config['acclen'])

    ## Use the same coefficients for both polarizations
    #if not testmode:
    #    feng.eq_load_coeffs(0, config['coeffs'])
    #    feng.eq_load_coeffs(1, config['coeffs'])

    #feng.eq_load_test_vectors(0, list(range(feng.n_chans_f)))
    #feng.eq_load_test_vectors(1, list(range(feng.n_chans_f)))
    #feng.eq_test_vector_mode(enable=tvg)
    try:
        fengs[0].spec_test_vector_mode(enable=tvg)
    except:
        pass

    try:
        for fn, feng in enumerate(fengs):
            if not testmode:
                feng.eq_load_coeffs(0, config['coeffs'])
                feng.eq_load_coeffs(1, config['coeffs'])
            feng.eq_load_test_vectors(0, list(range(feng.n_chans_f)))
            feng.eq_load_test_vectors(1, list(range(feng.n_chans_f)))
            feng.eq_test_vector_mode(enable=tvg)
    except:
        print("Failed to set Voltage test vector mode!")
        pass

    if eth_spec or eth_volt:
        # Configure arp table
        for ip, mac in config['arp'].items():
            print ("Configuring ip: %s with mac: %012x" %(ip, mac))
            for ethn, eth in enumerate(fengs[0].fpga.gbes):
                eth.set_single_arp_entry(ip, mac)

        voltage_config = config.get('voltage_output', None)
        n_interfaces = voltage_config.get('n_interfaces', fengs[0].n_interfaces)
        for i in range(n_interfaces):
            ip = config["interfaces"][fengs[0].fpga.host][i]
            mac = config["arp"][ip]
            port = 10000
            eth = fengs[0].fpga.gbes['eth%i_onehundred_gbe' %i]
            eth.configure_core(mac, ip, port)

    if eth_spec:
        config['spectrometer_dest'] = specdest or config['spectrometer_dest']
        for feng in fengs:
            feng.spec_set_pipeline_id()
            feng.spec_set_destination(config['spectrometer_dest'])

    if eth_volt:
        if voltage_config is not None:
            n_chans = voltage_config['n_chans']
            start_chan = voltage_config['start_chan']
            dests = voltage_config['dests']
            dests_is_antgroup_list_of_dests = isinstance(dests[0], list)
            chans_per_packet_limit = voltage_config['limit_chans_per_packet'] if 'limit_chans_per_packet'  in voltage_config else None
            logger.info('Voltage output sending channels %d to %d' % (start_chan, start_chan+n_chans-1))
            logger.info('Destination IPs: %s' %dests)
            logger.info('Using %d interfaces' % n_interfaces)
            for fn, feng in enumerate(fengs):
                dest_port = config['dest_port'][fn] if isinstance(config['dest_port'], list) else config['dest_port']
                feng_dests = dests if not dests_is_antgroup_list_of_dests else dests[fn]
                output = feng.select_output_channels(start_chan, n_chans, feng_dests, n_interfaces=n_interfaces, dest_ports=dest_port, nchans_per_packet_limit=chans_per_packet_limit)
                print(output)
            # hack to fill in channel reorder map for unused F-engines
            orig_pipeline_id = fengs[-1].pipeline_id
            orig_feng_id = fengs[-1].feng_id
            for fn, pipeline_id in enumerate(range(orig_pipeline_id+1, fengs[-1].n_ants_per_board)):
                dest_port = config['dest_port'][pipeline_id] if isinstance(config['dest_port'], list) else config['dest_port']
                feng_dests = dests if not dests_is_antgroup_list_of_dests else dests[fn]
                fengs[-1].feng_id = -1
                fengs[-1].pipeline_id = pipeline_id
                fengs[-1].select_output_channels(start_chan, n_chans, feng_dests, n_interfaces=n_interfaces, dest_ports=dest_port, blank=not noblank, nchans_per_packet_limit=chans_per_packet_limit)
            fengs[-1].pipeline_id = orig_pipeline_id
            fengs[-1].feng_id = orig_feng_id
        else:
            logger.error("Requested voltage output but config file did not provide a configuration")

    if eth_spec:
        for fn, feng in enumerate(fengs):
            feng.eth_set_dest_port(config['dest_port'][fn])

    #if eth_spec:
    #    feng.eth_set_mode('spectra')
    #    #feng.fpga.write_int('corr_feng_id', feng_id)
    #elif eth_volt:
    #    feng.eth_set_mode('voltage')

    if sync:
        if not mansync:
            fengs[0].sync_wait_for_pps()
        fengs[0].sync_arm(manual_trigger=mansync)
        for fn, feng in enumerate(fengs):
            feng.fft_of_detect_reset()

    # Reset ethernet cores prior to enabling
    if eth_spec or eth_volt:
        fengs[0].eth_reset()
        logger.info('Enabling Ethernet output')
        fengs[0].eth_enable_output(True)
    else:
        logger.info('Not enabling Ethernet output, since neither voltage or spectrometer 10GbE output flags were set.')

    logger.info("Initialization complete!")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Program and initialize a SNAP ADC5G spectrometer',
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('host', type=str,
                        help = 'Hostname / IP of RFSoC')
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
    parser.add_argument('-i', dest='feng_ids', type=int, nargs='*', default=[0,1,2,3],
                        help='List of F-engine IDs to write to this SNAP\'s output packets')
    parser.add_argument('-j', dest='pipeline_ids', type=int, nargs='*', default=[0,1,2,3],
                        help='List of pipeline IDs to associate an F-eng with a pipeline instance')
    parser.add_argument('-p', dest='dest_port', type=str,
                        default=None,
                        help='Comma-separated 100 GBe destination ports. One per F-engine [defaults to config file].')
    parser.add_argument('--skipprog', dest='skipprog', action='store_true', default=False,
                        help='Skip programming .fpg file')
    parser.add_argument('--eth_spec', dest='eth_spec', action='store_true', default=False,
                        help ='Use this flag to switch on Ethernet transmission of the spectrometer')
    parser.add_argument('--noblank', dest='noblank', action='store_true', default=False,
                        help ='Use this flag to send packets for dummy F-engines (labeled with FID 65535)')
    parser.add_argument('--eth_volt', dest='eth_volt', action='store_true', default=False,
                        help ='Use this flag to switch on Ethernet transmission of F-engine data')
    parser.add_argument('-a', dest='acclen', type=int, default=250000,
                        help ='Number of spectra to accumulate per spectrometer dump.')
    parser.add_argument('--testmode', dest='testmode', action='store_true',
                        help ='If True, only initialize registers present in the test firmware design')
    parser.add_argument('--specdest', dest='specdest', type=str, default=None,
            help ='Destination IP address to which spectra should be sent. Default: get from config file')

    args = parser.parse_args()

    run(args.host, args.fpgfile, args.configfile,
        sync=args.sync,
        mansync=args.mansync,
        tvg=args.tvg,
        feng_ids=args.feng_ids,
        pipeline_ids=args.pipeline_ids,
        dest_port=args.dest_port,
        skipprog=args.skipprog,
        eth_spec=args.eth_spec,
        noblank=args.noblank,
        eth_volt=args.eth_volt,
        acclen=args.acclen,
        testmode=args.testmode,
        specdest=args.specdest)
