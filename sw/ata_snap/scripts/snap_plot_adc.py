#! /usr/bin/env python

import argparse
import adc5g
import casperfpga
import time
import numpy as np
import matplotlib.pyplot as plt
import struct

parser = argparse.ArgumentParser(description='Plot ADC Histograms and Spectra',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('host', type=str,
                    help = 'Hostname / IP of SNAP')
parser.add_argument('fpgfile', type=str,
                    help = '.fpgfile to program')
parser.add_argument('-n', dest='numsnaps', type=int, default=1,
                    help ='Number of data snapshots to grab. More takes longer, but gets better statistics')
parser.add_argument('-s', dest='srate', type=float, default=900.0,
                    help ='Sample rate in MHz for non-interleaved band. Used for spectrum axis scales')
parser.add_argument('-i', dest='interleave', action='store_true', default=False,
                    help ='Interleave data from pairs of ADC cores (even the cores not used in the downstream firmware')

args = parser.parse_args()

print "Connecting to %s" % args.host
snap = casperfpga.CasperFpga(args.host)
print "Interpretting design data for %s with %s" % (args.host, args.fpgfile)
snap.get_system_information(args.fpgfile)

chani = []
chanq = []
speci = []
specq = []
for i in range(args.numsnaps):
    print "Grabbing ADC data (%d of %d)" % (i+1, args.numsnaps)
    all_chan_data = adc5g.get_snapshot(snap, 'ss_adc')
    #x,t= snap.snapshots.ss_adc.read_raw(man_trig=True, man_valid=True)
    #all_chan_data = struct.unpack('<%db' % x['length'], x['data'])
    #a = all_chan_data[0::4]
    #b = all_chan_data[1::4]
    #c = all_chan_data[2::4]
    #d = all_chan_data[3::4]
    #plt.subplot(4,1,1)
    #plt.semilogy(np.fft.fftshift(np.fft.rfft(a))**2)
    #plt.subplot(4,1,2)
    #plt.semilogy(np.fft.fftshift(np.fft.rfft(b))**2)
    #plt.subplot(4,1,3)
    #plt.semilogy(np.fft.fftshift(np.fft.rfft(c))**2)
    #plt.subplot(4,1,4)
    #plt.semilogy(np.fft.fftshift(np.fft.rfft(d))**2)
    #plt.show()
    #exit()
    
    # Separate data into multiple channels
    if args.interleave:
        chani += [all_chan_data[0::2]]
        chanq += [all_chan_data[1::2]]
    else:
        chani += [all_chan_data[0::2][0::2]]
        chanq += [all_chan_data[1::2][0::2]]
    speci += [np.abs(np.fft.rfft(chani[-1]))**2]
    specq += [np.abs(np.fft.rfft(chanq[-1]))**2]

chani = np.array(chani)
chanq = np.array(chanq)
speci = np.array(speci)
specq = np.array(specq)

if args.interleave:
    frange = np.linspace(0, args.srate*2/2, speci.shape[1])
else:
    frange = np.linspace(0, args.srate/2, speci.shape[1])

fig, ax = plt.subplots(2,1)
fig.suptitle("Channel I")
ax[0].hist(chani.flatten(), bins=range(-128,128))
ax[0].set_xlabel("ADC value")
ax[1].semilogy(frange, speci.mean(axis=0))
ax[1].set_xlabel("Frequency [MHz]")
print "Channel I ADC mean/std-dev: %.2f / %.2f" % (chani.mean(), chani.std())

fig, ax = plt.subplots(2,1)
fig.suptitle("Channel Q")
ax[0].hist(chanq.flatten(), bins=range(-128,128))
ax[0].set_xlabel("ADC value")
ax[1].semilogy(frange, specq.mean(axis=0))
ax[1].set_xlabel("Frequency [MHz]")
print "Channel Q ADC mean/std-dev: %.2f / %.2f" % (chanq.mean(), chanq.std())

plt.show()
