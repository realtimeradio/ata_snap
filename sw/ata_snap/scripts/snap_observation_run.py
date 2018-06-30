#! /usr/bin/env python
import os
import sys
from ata_snap import ata_control
from subprocess import Popen, PIPE
import argparse
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sh = logging.StreamHandler(sys.stdout)
logger.addHandler(sh)

#ch.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#ch.setFormatter(formatter)

parser = argparse.ArgumentParser(description='Run an observation with multiple antennas and pointings',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('host', type=str,
                    help = 'Hostname / IP of SNAP')
parser.add_argument('fpgfile', type=str,
                    help = '.fpgfile to program')
#parser.add_argument('-s', dest='srate', type=float, default=900.0,
#                    help ='Sample rate in MHz for non-interleaved band. Used for spectrum axis scales')
parser.add_argument('-n', dest='ncaptures', type=int, default=16,
                    help ='Number of data captures (for each correlation product)')
parser.add_argument('-r', dest='repetitions', type=int, default=4,
                    help ='Number of repetitions of on-off pairs')
parser.add_argument('-a', dest='ants', type=str, default='2a,2b,2e,3l,1f,5c,4l,4g',
                    help ='Comma separated list of ATA antennas, eg: \"2a,2b,2e\"')
parser.add_argument('-p', dest='pointings', type=str, default=None,
                    help ='Comma separated list of pointings. Format as <source>_<az offset>_<el_offset>, eg: \"casa,vira_10_0\"')
parser.add_argument('-o', dest='off', type=str, default=None,
                    help ='Use this flag to specify an off source position for each source, in the form <az_offset>_<el_offset>, eg: \"10_0\"')
parser.add_argument('-f', dest='freqs', type=str, default=None,
                    help ='Comma separated list of sky tuning frequencies, in MHz. Eg: \"2000,3000,4000\"')

args = parser.parse_args()

ants = args.ants.split(',')
pointings = args.pointings.split(',')
freqs = map(float, args.freqs.split())

logger.info("Reserving antennas %s in bfa antgroup" % str(ants))
ata_control.reserve_antennas(ants)

logger.info("Setting antenna attenuators to 15dB")
logger.info("Setting SPR attenuators to 0dB")
for ant in ants:
   ata_control.set_pam_atten(ant, "x", 15)
   ata_control.set_pam_atten(ant, "y", 15)
ata_control.set_atten(0, 0)
ata_control.set_atten(1, 0)

try:
    for pointing in pointings:
        pointing_spl = pointing.split('_')
        if len(pointing_spl) == 1:
            source = pointing
            az_offset = 0
            el_offset = 0
        else:
            source = pointing_spl[0]
            az_offset = pointing_spl[1]
            el_offset = pointing_spl[2]
        logger.info("Requested pointing is source: %s, az_offset: %.1f, el_offset: %.1f" % (source, az_offset, el_offset))
        for freq in freqs:
            logger.info("Requested tuning is %.2f" % freq)
            ata_control.write_obs_to_db(source, freq, az_offset, el_offset, ants)
            obsid = ata_control.get_latest_obs()
            logger.info("Obs ID is %d" % obsid)
            for antn, ant in enumerate(ants):
                for repetition in range(args.repetitions):
                    if args.off is not None:
                        off_az_off, off_el_off = map(float, args.off.split('_'))
                        for onoff in ["on", "off"]:
                            logger.info("Capturing data for antenna %s, %s iteration %d" % (ant, onoff, repetition))
                            if onoff == "on":
                                ata_control.point(source, freq)
                            elif onoff == "off":
                                ata_control.point(source, freq, off_az_off, off_el_off)
                            ata_control.set_rf_switch(0, antn)
                            ata_control.set_rf_switch(1, antn)
                            proc = Popen(["python", "snap_take_spec_data.py", args.host, args.fpgfile, "-n", "%d" % args.ncaptures, "-a", ant, "-c", "%s_%s%d_ant_%s_%.2f_obsid%d" % (source, onoff, repetition, ant, freq, obsid)])
                            proc.wait()
                    else:
                        onoff = "on"
                        logger.info("Capturing data for antenna %s, %s iteration %d" % (ant, onoff, repetition))
                        ata_control.point(source, freq)
                        ata_control.rf_switch_ant(ant, 'x')
                        ata_control.rf_switch_ant(ant, 'y')
                        proc = Popen(["python", "snap_take_spec_data.py", args.host, args.fpgfile, "-n", "%d" % args.ncaptures, "-a", ant, "-c", "%s_%s%d_ant_%s_%.2f_obsid%d" % (source, onoff, repetition, ant, freq, obsid)])
                        proc.wait()
            ata_control.end_obs()
except KeyboardInterrupt:
    exit()

