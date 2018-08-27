#! /usr/bin/env python

import argparse
import adc5g
import casperfpga
import time
import numpy as np
import matplotlib.pyplot as plt
from ata_snap import ata_control
import struct

parser = argparse.ArgumentParser(description='Set attenuator values to a target power level',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('host', type=str,
                    help = 'Hostname / IP of SNAP')
parser.add_argument('fpgfile', type=str,
                    help = '.fpgfile to program')
parser.add_argument('-n', dest='numsnaps', type=int, default=1,
                    help ='Number of data snapshots to grab. More takes longer, but gets better statistics')
parser.add_argument('-a', dest='ant', type=str, default="2j",
                    help ='Antenna to tune')
parser.add_argument('-r', dest='rms', type=float, default=12.0,
                    help ='Target RMS')

args = parser.parse_args()

print "Connecting to %s" % args.host
snap = casperfpga.CasperFpga(args.host)
print "Interpretting design data for %s with %s" % (args.host, args.fpgfile)
snap.get_system_information(args.fpgfile)

atteni = 0
attenq = 0
max_attempts = 5
for attempt in range(max_attempts):
    ata_control.set_atten_by_ant(args.ant + "x", atteni)
    ata_control.set_atten_by_ant(args.ant + "y", attenq)
    chani = []
    chanq = []
    speci = []
    specq = []
    for i in range(args.numsnaps):
        all_chan_data = adc5g.get_snapshot(snap, 'ss_adc')
        
        chani += [all_chan_data[0::2][0::2]]
        chanq += [all_chan_data[1::2][0::2]]
        speci += [np.abs(np.fft.rfft(chani[-1]))**2]
        specq += [np.abs(np.fft.rfft(chanq[-1]))**2]
    
    chani = np.array(chani)
    chanq = np.array(chanq)
    speci = np.array(speci)
    specq = np.array(specq)

    print "Channel I ADC mean/std-dev: %.2f / %.2f" % (chani.mean(), chani.std())
    print "Channel Q ADC mean/std-dev: %.2f / %.2f" % (chanq.mean(), chanq.std())

    delta_atteni = 20*np.log10(chani.std() / args.rms)
    delta_attenq = 20*np.log10(chanq.std() / args.rms)

    if (delta_atteni < 1) and (delta_attenq < 1):
        print "Exiting"
        exit()
    else:
        # Attenuator has 0.25dB precision
        atteni = int(4 * (atteni + delta_atteni)) / 4.0
        attenq = int(4 * (attenq + delta_attenq)) / 4.0
        if atteni > 30:
            atteni = 30
        if attenq > 30:
            attenq = 30
        print "New X-attenuation: %.3f" % atteni
        print "New Y-attenuation: %.3f" % attenq
print "Exiting after %d tuning attempts" % attempt
