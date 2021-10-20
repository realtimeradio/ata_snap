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
    h = {}
    h['timestamp'] = header[5]
    h['feng_id'] = header[4]
    h['chan']    = header[3]
    h['n_chans'] = header[2]
    h['type']    = header[1]
    h['version'] = header[0]
    if h['type'] & 0b10:
        d = np.fromstring(pkt[16:], dtype=">B")
        d = d[0::2] + 1j*d[1::2]
        #d = np.fromstring(pkt[16:], dtype=">H")
        #dr = (d >> 8) & 0xff
        #di = d & 0xff
        #d4bit = ((dr >> 4) << 4) + (di >> 4)
        #d = d4bit
    else:
        d = np.fromstring(pkt[16:], dtype=">B")
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
        print('X:')
        for i in range(8):
            for j in range(16):
                print(x[16*i + j], end=' ')
            print()
        print('X:')
        for i in range(8):
            for j in range(16):
                print(y[16*i + j], end=' ')
            print()
except KeyboardInterrupt:
    pass
