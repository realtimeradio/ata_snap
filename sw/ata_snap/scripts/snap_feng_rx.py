#! /usr/bin/env python
import socket
import struct
import numpy as np
import time
import sys
import os
import argparse
from ata_snap import ata_control
from subprocess import Popen

RXBUF = 8500

def unpack(pkt):
    header = struct.unpack(">BBHHHQ", pkt[0:16])
    d = np.frombuffer(pkt[16:], dtype=">B")
    h = {}
    h['timestamp'] = header[5]
    h['feng_id'] = header[4]
    h['chan']    = header[3]
    h['n_chans'] = header[2]
    h['type']    = header[1]
    h['version'] = header[0]
    #h['feng_id'] = header[0] & 0xffff
    #h['chan']    = (header[0] >> 16) & 0xffff
    #h['n_chans'] = (header[0] >> 32) & 0xffff
    #h['type']    = (header[0] >> 48) & 0xff
    #h['version'] = (header[0] >> 56) & 0xff
    x = d[0::2]
    y = d[1::2]
    return h, x, y

parser = argparse.ArgumentParser(description='Start a process to capture SNAP F-engine packets',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-i', dest='ip', type=str, default='100.100.10.1',
                    help ='IP address on which to receive')
parser.add_argument('-p', dest='port', type=int, default=10000,
                    help ='UDP port on which to receive')
parser.add_argument('-f', dest='fname', type=str, default=None,
                    help ='Filename in which to dump packets')
parser.add_argument('-t', dest='recordtime', type=int, default=20,
                    help ='Number of seconds to record for')

args = parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((args.ip, args.port))

print("Receiving on %s:%d" % (args.ip, args.port))

starttime = time.time()
treport = time.time()
last_t = 0
n = 0
if args.fname is not None:
    print("Writing to file %s" % args.fname)
    fh = open(args.fname, 'wb')
try:
    tick = time.time()
    while(True):
        data = sock.recv(RXBUF)
        if (n % 100000) == 0:
            h, x, y = unpack(data)
            this_t = h['timestamp']
            print(time.ctime(), "Packets received:", n, "This packet:", this_t, "(Diff: %d)" % (this_t - last_t))
            last_t = this_t
            if time.time() > (starttime + args.recordtime):
                break
        n = n+1
        if args.fname is None:
            h, x, y = unpack(data)
            print(h)
            for i in range(32):
                print(x[i], end=' ')
            print('|', end=' ')
            for i in range(32):
                print(y[i], end=' ')
            print()
        else:
            fh.write(data)
except KeyboardInterrupt:
    pass

if args.fname is not None:
    fh.close()
