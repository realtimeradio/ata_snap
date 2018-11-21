#! /usr/bin/env python
import socket
import numpy as np
import time
import sys
import os
import argparse
from ata_snap import ata_control
from subprocess import Popen

parser = argparse.ArgumentParser(description='Start a process to write 10GbE SNAP data to disk',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('filename', type=str,
                    help = 'filename where data resides')
parser.add_argument('starttime', type=float,
                    help = 'unix timestamp of observation start')
parser.add_argument('-s', dest='source', type=str, default="psrb0329+54",
                    help ='Source name (as per ATA catalog calls)')
parser.add_argument('-a', dest='acc_len', type=int, default=1024,
                    help ='Accumulation length, in spectra')
parser.add_argument('-n', dest='n_chan', type=int, default=2048,
                    help ='Number of channels in a spectrum')
parser.add_argument('-f', dest='srate', type=float, default=838.8608,
                    help ='Accumulation length, in spectra')
parser.add_argument('-r', dest='rfc', type=float, default=3500.0,
                    help ='RF centre frequency in MHz')
parser.add_argument('-i', dest='ifc', type=float, default=629.1452,
                    help ='IF centre frequency in MHz')
parser.add_argument('-F', dest='flip', action="store_true", default=False,
                    help ='IF centre frequency in MHz')


args = parser.parse_args()


print "Making filterbank header"
ra, dec = ata_control.get_ra_dec(args.source, deg=False)
fbhdr_filename = args.filename + ".fbhdr"
fb_args = [
  "-o", fbhdr_filename,
  "-nifs", "1",
  "-fch1", "%8f" % (args.rfc - args.srate/2. + args.ifc),
  "-source", args.source.strip("psr").upper(),
  "-filename", args.filename,
  "-telescope", "ATA",
  "-src_raj", ra.replace(":",""),
  "-src_dej", dec.replace(":",""),
  "-tsamp", "%.8f" % (args.acc_len * args.n_chan * 2 / args.srate), # outputs micrpsecs for srate in MHz
  "-foff", "%.8f" % (-args.srate / 2. / args.n_chan), # in MHz for srate in MHz
  "-nbits", "32",
  "-nchans", "%d" % args.n_chan,
  "-tstart", "%.8f" % (args.starttime / 86400. + 40587),
]
print "Making filterbank header with arguments:"
print fb_args

proc = Popen(["filterbank_mkheader"] + fb_args)
proc.wait()

print "Reading header file"
with open(args.filename, "rb") as fh:
    data = fh.read()
print "Reading data file"
with open(fbhdr_filename, "rb") as fh:
    header = fh.read()
print "Writing filterbank file"
with open(args.filename + ".fil", "wb") as fh:
    fh.write(header + data)
