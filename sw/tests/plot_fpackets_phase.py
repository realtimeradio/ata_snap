import argparse
import numpy as np
import sys
import scapy.all as sc
import struct
import matplotlib.pyplot as plt

NCHAN = 32
NTIME = 16
NPOL = 2
NBYTE = 2
HEADER_BYTES = 16
WINDOW_SIZE = 10000

def decode_packet(pkt):
    header = struct.unpack(">BBHHHQ", pkt[0:HEADER_BYTES])
    d = np.frombuffer(pkt[HEADER_BYTES:], dtype=">b")
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
    xr = d[0::4]
    xi = d[1::4]
    yr = d[2::4]
    yi = d[3::4]
    x = (xr + 1j*xi).reshape(NCHAN, NTIME)
    y = (yr + 1j*yi).reshape(NCHAN, NTIME)
    return h, x, y


def main():
    parser = argparse.ArgumentParser(description='Examine F-packets',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-f', dest='fname', type=str, default=None,
                        help ='Filename in which to dump packets')
    parser.add_argument('-t', dest='target_mcnt', type=int, default=None,
                        help ='Target MCNT about which to examine')
    
    args = parser.parse_args()
    t = []
    p = []
    fh = open(args.fname, 'rb')
    packet_size = NCHAN * NTIME * NPOL * NBYTE + HEADER_BYTES
    print("Opening file %s" % args.fname)
    print("Packet size is %d bytes" % packet_size)
    pn = 0
    if args.target_mcnt is not None:
        d = fh.read(packet_size)
        h, x, y = decode_packet(d)
        print("First packet timestamp is %d" % h['timestamp'])
        t_offset = args.target_mcnt - h['timestamp']
        if t_offset < 0:
            print("Target timestamp (%d) not in file!" % args.target_mcnt)
            fh.close()
            exit()
        p_offset = t_offset // NTIME
        print("Packet offset is %d" % p_offset)
        if p_offset < WINDOW_SIZE:
            p_offset = 0
        else:
            p_offset = p_offset - WINDOW_SIZE
        fh.seek(p_offset * packet_size)
        # HACK
        # Sometimes packets at the beginning of a capture are missing. Go backwards if necessary
        d = fh.read(packet_size)
        h, x, y = decode_packet(d)
        if h['timestamp'] > args.target_mcnt:
            p_offset = p_offset - ((h['timestamp'] - args.target_mcnt) // NTIME) - WINDOW_SIZE
            fh.seek(p_offset * packet_size)
    while(True):
        d = fh.read(packet_size)
        if len(d) < packet_size:
            break
        if args.target_mcnt is not None:
            if pn > 2*WINDOW_SIZE:
                break
        h, x, y = decode_packet(d)
        print(h['timestamp'])
        #if pn % 10000 == 0:
        #    print(h['timestamp'])
        for i in range(NTIME):
            t += [h['timestamp'] + i]
            p += [np.angle(x[:,i] * np.conj(y[:,i]))]
        pn += 1
        #if pn > 1000:
        #    print(x[0:20])
        #    print(y[0:20])
        #    break
        #print(h['timestamp'])
        #print(x[0:20])
        #print(y[0:20])
    p = np.array(p)
    t = np.array(t)
    #for chan in range(0,10):
    nchans = p.shape[1]
    if args.target_mcnt is not None:
        t_origin = args.target_mcnt
    else:
        t_origin = t[0]
    for c in range(4):
        plt.plot(t - t_origin, p[:,c], '-o', label='Channel %d' % c)
    plt.plot(t - t_origin, p[:,nchans-1], '-o', label='Channel %d' % (nchans-1))
    #if args.target_mcnt is not None:
    #    plt.xlim((- 5, 5))
    plt.xlabel('Timestamp - %d' % t_origin)
    plt.ylabel('Phase')
    plt.legend()
    plt.show()
    fh.close()

if __name__ == "__main__":
    main()

    
