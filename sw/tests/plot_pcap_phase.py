import numpy as np
import sys
import scapy.all as sc
import struct
import matplotlib.pyplot as plt

def decode_packet(pkt):
    header = struct.unpack(">BBHHHQ", pkt[0:16])
    d = np.frombuffer(pkt[16:], dtype=">b")
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
    xr = d[0::4][0::16]
    xi = d[1::4][0::16]
    yr = d[2::4][0::16]
    yi = d[3::4][0::16]
    return h, xr + 1j*xi, yr + 1j*yi

def main(fname):
    t = []
    p = []
    packets = sc.PcapReader(fname)
    for pn, packet in enumerate(packets):
        h, x, y = decode_packet(bytes(packet['UDP'].payload))
        if pn % 10000 == 0:
            print(h['timestamp'])
        if h['timestamp'] < 1360100000:
            continue
        if h['timestamp'] > 1360400000:
            break
        t += [h['timestamp']]
        p += [np.angle(x * np.conj(y))]
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
    plt.plot(t - t[0], p[:,0], label='Channel %d' % 0)
    plt.plot(t - t[0], p[:,nchans-1], label='Channel %d' % nchans)
    plt.xlabel('Timestamp - %d' % t[0])
    plt.ylabel('Phase')
    plt.legend()
    plt.show()

if __name__ == "__main__":
    main(sys.argv[1])

    
