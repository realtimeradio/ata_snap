#! /usr/bin/env python

def get_data(snap, auto_cross):
    x,t = snap.snapshots.vacc_ss_ss.read_raw()
    d = np.array(struct.unpack('>%dl' % (x['length']/4), x['data']))
    # Calculate Frequency scale of plots
    # d array holds twice as many values as there are freq channels (either xx & yy, or xy_r & xy_i
    frange = np.linspace(args.rfc - (args.srate - args.ifc), args.rfc - (args.srate - args.ifc) + args.srate/2., d.shape[0]/2)
    # Make two plots -- either xx, yy. Or abs(xy), phase(xy)
    if auto_cross == "auto":
        xx = d[0::2]
        yy = d[1::2]
        return frange, 10*np.log10(xx), 10*np.log10(yy)
    else:
        xy = np.array(d[0::2] + 1j*d[1::2], dtype=np.complex32)
        return frange, 10*np.log10(np.abs(xy)), np.angle(xy)

import argparse
import casperfpga
import time
import numpy as np
import matplotlib.pyplot as plt
import struct
import ata_control

parser = argparse.ArgumentParser(description='Plot ADC Histograms and Spectra',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('host', type=str,
                    help = 'Hostname / IP of SNAP')
parser.add_argument('fpgfile', type=str,
                    help = '.fpgfile to program')
parser.add_argument('-a', dest='ant', type=str, default="0",
                    help ='Which antenna to plot. "auto" or "cross"')
parser.add_argument('-s', dest='srate', type=float, default=900.0,
                    help ='Sample rate in MHz for non-interleaved band. Used for spectrum axis scales')
parser.add_argument('-r', dest='rfc', type=float, default=None,
                    help ='RF centre frequency in MHz. If None, will read from the ATA control system')
parser.add_argument('-i', dest='ifc', type=float, default=629.1452,
                    help ='IF centre frequency in MHz')

args = parser.parse_args()

assert args.ant in ["auto", "cross"]

if args.rfc is None:
    try:
        print "Trying to get sky frequency tuning from ATA control system"
        args.rfc = ata_control.get_sky_freq()
    except:
        print "Failed! Using default tuning of 629.1452 MHz"
        args.rfc = 629.1452

print "Using RF center frequency of %.2f" % args.rfc
print "Using IF center frequency of %.2f" % args.ifc


print "Connecting to %s" % args.host
snap = casperfpga.CasperFpga(args.host)
print "Interpretting design data for %s with %s" % (args.host, args.fpgfile)
snap.get_system_information(args.fpgfile)

print "Figuring out accumulation length"
acc_len = float(snap.read_int('timebase_sync_period') / (4096 / 4))
print "Accumulation length is %f" % acc_len

mux_sel = {'auto':0, 'cross':1}
print "Setting snapshot select to %s (%d)" % (args.ant, mux_sel[args.ant])
snap.write_int('vacc_ss_sel', mux_sel[args.ant])


plt.ion()
fig, ax = plt.subplots(2,1)
# initialize axis labels
if args.ant == "auto":
    ax[0].set_ylabel("Power [dB arb. ref.]")
    ax[1].set_ylabel("Power [dB arb. ref.]")
    ax[1].set_xlabel("Frequency [MHz]")
else:
    ax[0].set_ylabel("Power [dB arb. ref.]")
    ax[1].set_ylabel("Phase [radians]")
    ax[1].set_xlabel("Frequency [MHz]")

# Update plot contents
while(True):
    try:
        frange, d0, d1 = get_data(snap, args.ant)
        ax[0].clear()
        ax[1].clear()
        ax[0].plot(frange, d0)
        ax[1].plot(frange, d1)
        fig.canvas.draw()
    except KeyboardInterrupt:
        exit()
