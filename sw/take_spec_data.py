#! /usr/bin/env python
import os
from subprocess import Popen, PIPE
import argparse
import casperfpga
import adc5g
import time
import numpy as np
import matplotlib.pyplot as plt
import struct
import cPickle as pkl

parser = argparse.ArgumentParser(description='Plot ADC Histograms and Spectra',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('host', type=str,
                    help = 'Hostname / IP of SNAP')
parser.add_argument('fpgfile', type=str,
                    help = '.fpgfile to program')
parser.add_argument('-s', dest='srate', type=float, default=900.0,
                    help ='Sample rate in MHz for non-interleaved band. Used for spectrum axis scales')
parser.add_argument('--nox', dest='nox', action='store_true', default=False,
                    help ='Do not record X-pol data')
parser.add_argument('--noy', dest='noy', action='store_true', default=False,
                    help ='Do not record Y-pol data')
parser.add_argument('-n', dest='ncaptures', type=int, default=16,
                    help ='Number of data captures (for each correlation product)')
parser.add_argument('-r', dest='rfc', type=float, default=0.0,
                    help ='RF centre frequency in MHz. 0 => Grab the frequency from the ATA control system')
parser.add_argument('-i', dest='ifc', type=float, default=629.1452,
                    help ='IF centre frequency in MHz')
parser.add_argument('-c', dest='comment', type=str, default="",
                    help ='comment to be appended at the end of the filename (eg, a source name)')
parser.add_argument('-p', dest='path', type=str, default="~/data",
                    help ='Directory in which to record data')

args = parser.parse_args()
out = vars(args).copy()

if args.rfc == 0.0:
    print "Reading Sky center frequency from the ATA control system"
    loproc = Popen(["atagetskyfreq", "a"], stdout=PIPE, stderr=PIPE)
    stdout, stderr = loproc.communicate()
    out["rfc"] = float(stdout.strip())
    print "Frequency is %.1f MHz" % out["rfc"]

print "Trying to get ATA status information"
try:
    atastat = Popen("ataasciistatus", stdout=PIPE, stderr=PIPE)
    stdout, stderr = atastat.communicate()
    print "Succeeded -- status will be written into the output file"
    out['ata_status'] = stdout
except:
    print "!!!!!!!!!!!!!!!!!!!!!!!!"
    print "!!!!!!   Failed   !!!!!!"
    print "!!!!!!!!!!!!!!!!!!!!!!!!"


datadir = os.path.expanduser(args.path)

if not os.path.isdir(datadir):
    print "Chosen data directory: %s does not exist. Create it and run this script again!" % datadir
    exit()

filename = os.path.join(datadir, "%d_rf%.2f_n%d_%s.pkl" % (time.time(), out['rfc'], args.ncaptures, args.comment))
print "Output filename is %s" % filename

print "Using RF center frequency of %.2f" % out['rfc']
print "Using IF center frequency of %.2f" % args.ifc

print "Connecting to %s" % args.host
snap = casperfpga.CasperFpga(args.host)
print "Interpretting design data for %s with %s" % (args.host, args.fpgfile)
snap.get_system_information(args.fpgfile)


print "Figuring out accumulation length"
acc_len = float(snap.read_int('timebase_sync_period') / (4096 / 4))
print "Accumulation length is %f" % acc_len

print "Estimating FPGA clock"
fpga_clk = snap.estimate_fpga_clock()
out['fpga_clk'] = fpga_clk
print "Clock estimate is %.1f" % fpga_clk
assert np.abs((fpga_clk*4. / args.srate) - 1) < 0.01

mux_sel = {'0':0, '1':1, 'cross_even':2, 'cross_odd':3}

print "Grabbing ADC statistics to write to file"
adc0 = []
adc1 = []
for i in range(10):
    all_chan_data = adc5g.get_snapshot(snap, 'ss_adc')
    adc0 += [all_chan_data[0::2][0::2]]
    adc1 += [all_chan_data[1::2][0::2]]

adc0 = np.array(adc0)
adc1 = np.array(adc1)

out["adc0_bitsnaps"] = adc0
out["adc1_bitsnaps"] = adc1
out["adc0_stats"] = {"mean": adc0.mean(), "dev": adc0.std()}
out["adc1_stats"] = {"mean": adc1.mean(), "dev": adc1.std()}

print "ADC0 mean/dev: %.2f / %.2f" % (out["adc0_stats"]["mean"], out["adc0_stats"]["dev"])
print "ADC1 mean/dev: %.2f / %.2f" % (out["adc1_stats"]["mean"], out["adc1_stats"]["dev"])

out['fft_shift'] = snap.read_int('fft_shift')

ants = []
if not args.nox:
    ants += '0'
    out['auto0'] = []
    out['auto0_timestamp'] = []
    out['auto0_of_count'] = []
    out['fft_of0'] = []
if not args.noy:
    ants += '1'
    out['auto1'] = []
    out['auto1_timestamp'] = []
    out['auto1_of_count'] = []
    out['fft_of1'] = []

for i in range(args.ncaptures):
    for ant in ants:
        print "Setting snapshot select to %s (%d)" % (ant, mux_sel[ant])
        snap.write_int('vacc_ss_sel', mux_sel[ant])
        print "Grabbing data (%d of %d)" % (i+1, args.ncaptures)
        x,t = snap.snapshots.vacc_ss_ss.read_raw()
        d = np.array(struct.unpack('>%dl' % (x['length']/4), x['data'])) / acc_len * 2**18.
        frange = np.linspace(out['rfc'] - (args.srate - args.ifc), out['rfc'] - (args.srate - args.ifc) + args.srate/2., d.shape[0])
        out['frange'] = frange
        out['auto%s' % ant] += [d]
        out['auto%s_timestamp' % ant] += [t]
        out['auto%s_of_count' % ant] += [snap.read_int('power_vacc%s_of_count' % ant)]
        out['fft_of%s' % ant] += [snap.read_int('fft_of')]

print "Dumping data to %s" % filename
pkl.dump(out, open(filename, 'w'))
