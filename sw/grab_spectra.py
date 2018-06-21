#! /usr/bin/env python

import argparse
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
parser.add_argument('-a', dest='ant', type=str, default=1,
                    help ='Which antenna to plot. 0, 1, or "cross_even", "cross_odd"')
parser.add_argument('-s', dest='srate', type=float, default=900.0,
                    help ='Sample rate in MHz for non-interleaved band. Used for spectrum axis scales')
parser.add_argument('-r', dest='rfc', type=float, default=1419.0,
                    help ='RF centre frequency in MHz')
parser.add_argument('-i', dest='ifc', type=float, default=629.1452,
                    help ='IF centre frequency in MHz')

args = parser.parse_args()

assert args.ant in ['0', '1', 'cross_even', 'cross_odd']

print "Using RF center frequency of %.2f" % args.rfc
print "Using IF center frequency of %.2f" % args.ifc

print "Connecting to %s" % args.host
snap = casperfpga.CasperFpga(args.host)
print "Interpretting design data for %s with %s" % (args.host, args.fpgfile)
snap.get_system_information(args.fpgfile)

print "Figuring out accumulation length"
acc_len = float(snap.read_int('timebase_sync_period') / (4096 / 4))
print "Accumulation length is %f" % acc_len

mux_sel = {'0':0, '1':1, 'cross_even':2, 'cross_odd':3}
print "Setting snapshot select to %s (%d)" % (args.ant, mux_sel[args.ant])
snap.write_int('vacc_ss_sel', mux_sel[args.ant])

print "Snapping data"
x,t = snap.snapshots.vacc_ss_ss.read_raw()
d = np.array(struct.unpack('>%dl' % (x['length']/4), x['data'])) / acc_len * 2**18.
if args.ant in ['0', '1']:
    frange = np.linspace(args.rfc - (args.srate - args.ifc), args.rfc - (args.srate - args.ifc) + args.srate/2., d.shape[0])
    fig, ax = plt.subplots(1,1)
    ax.semilogy(frange, d)
    ax.set_xlabel('Frequency [MHz]')
else:
    d = np.array(d[0::2] + 1j*d[1::2], dtype=np.complex32)
    frange = np.linspace(args.rfc - (args.srate - args.ifc), args.rfc - (args.srate - args.ifc) + args.srate/2., d.shape[0])
    fig, ax = plt.subplots(2,1)
    ax[0].semilogy(frange, np.abs(d))
    ax[0].set_ylabel('Power')
    ax[1].plot(frange, np.angle(d))
    ax[1].set_ylabel('Phase')
    ax[1].set_xlabel('Frequency [MHz]')

plt.show()
