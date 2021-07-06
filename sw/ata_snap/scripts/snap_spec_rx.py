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
    header = struct.unpack(">Q", pkt[0:8])[0]
    #header = struct.unpack(">Q", pkt[0:64][::-1][0:8])[0]
    d = np.fromstring(pkt[8:], dtype="<f") * 2**63
    h = {}
    h['feng_id'] = header & 0xff
    h['block_index'] = (header >> 8) & 0x7
    h['acc_id'] = (header >> 11) & (2**45 -1)
    h['version'] = (header >> 56) & 0xff
    #h['feng_id'] = header[0] & 0xffff
    #h['chan']    = (header[0] >> 16) & 0xffff
    #h['n_chans'] = (header[0] >> 32) & 0xffff
    #h['type']    = (header[0] >> 48) & 0xff
    #h['version'] = (header[0] >> 56) & 0xff
    x = d[0::4]
    y = d[1::4]
    xy_r = d[2::4]
    xy_i = d[3::4]
    return h, x, y, xy_r, xy_i

parser = argparse.ArgumentParser(description='Start a process to capture SNAP F-engine packets',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-i', dest='ip', type=str, default='100.100.10.1',
                    help ='IP address on which to receive')
parser.add_argument('-p', dest='port', type=int, default=10000,
                    help ='UDP port on which to receive')
parser.add_argument('--printone', action='store_true',
                    help ='print a single packet from each source and integration')
parser.add_argument('-d', dest='print_data', action='store_true',
                    help ='Print snippet of packet data')

args = parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((args.ip, args.port))

print("Receiving on %s:%d" % (args.ip, args.port))

starttime = time.time()

try:
    tick = time.time()
    while(True):
        data = sock.recv(RXBUF)
        h, x, y, xy_r, xy_i = unpack(data)
        if not args.printone or h['block_index'] == 0:
            print(time.time(), h)
        if args.print_data:
            print('x', x[0:10])
            print('y', y[0:10])
            print('xy_r', xy_r[0:10])
            print('xy_i', xy_i[0:10])
        #for i in range(32):
        #    print(x[i], end=' ')
        #print('|', end=' ')
        #for i in range(32):
        #    print(y[i], end=' ')
        #print()
except KeyboardInterrupt:
    pass
