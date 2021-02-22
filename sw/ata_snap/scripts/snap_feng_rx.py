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
    d = np.fromstring(pkt[16:], dtype=">B")
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

args = parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((args.ip, args.port))

print("Receiving on %s:%d" % (args.ip, args.port))

starttime = time.time()

try:
    tick = time.time()
    while(True):
        data = sock.recv(RXBUF)
        h, x, y = unpack(data)
        print(h)
        for i in range(32):
            print(x[i], end=' ')
        print('|', end=' ')
        for i in range(32):
            print(y[i], end=' ')
        print()
except KeyboardInterrupt:
    pass
