import socket
import numpy as np
import time
import sys

PORT = 10000
IP = "10.10.10.131"
PACKETS_PER_SPECTRA = 4
PRINT_PACKETS = 1000
N_CHANNELS = 2048
N_STOKES_PER_PACKET = 4
BYTES_PER_WORD = 4
HEADER_BYTES = 8

bytes_per_packet = BYTES_PER_WORD * N_CHANNELS * N_STOKES_PER_PACKET / PACKETS_PER_SPECTRA + HEADER_BYTES
print "Bytes per packet: %d" % bytes_per_packet

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((IP, PORT))

fh = open("%s_%d.raw" % (sys.argv[1], time.time()), "w")

def unpack(pkt):
    header = np.fromstring(pkt[0:8], dtype=">L")
    d = np.fromstring(pkt[8:], dtype=">i")
    xx = d[1::4]
    yy = d[2::4]
    #xy_r = d[3::4]
    #xy_i = d[4::4]
    return header, xx, yy

pkt_cnt = 0
missing_packets_count = 0
try:
    tick = time.time()
    while(True):
        data = sock.recv(bytes_per_packet)
        h, xx, yy = unpack(data)
        if pkt_cnt != 0:
            if h != last_h + 1:
                missing_packets = h - last_h - 1
                missing_packets_count += missing_packets
                print "%d PACKETS LOST! (running total: %d)" % (missing_packets, missing_packets_count)
                fh.write('\x00' * (bytes_per_packet - HEADER_BYTES) * missing_packets)
                pkt_cnt += missing_packets
        last_h = h
        I = (np.array(xx, dtype=np.float32) + np.array(yy, dtype=np.float32)).tostring()
        pkt_cnt += 1
        if pkt_cnt % PRINT_PACKETS == 0:
            tock = time.time()
            n_spectra = pkt_cnt / PACKETS_PER_SPECTRA
            print "Received packet %d (spectra %d) (last %d spectra took %.1f seconds)" % (pkt_cnt, n_spectra, PRINT_PACKETS / PACKETS_PER_SPECTRA, tock-tick)
            tick = tock
        fh.write(I)
except KeyboardInterrupt:
    # Deal with the case of closing file
    # When we're mid way through a spectra
    straggling_packets = pkt_cnt % PACKETS_PER_SPECTRA
    for i in range(straggling_packets):
        fh.write(np.zeros(N_CHANNELS / PACKETS_PER_SPECTRA, dtype=np.float32).tostring())
    print ""
    print "Closing %s" % fh.name
    print "Recorded %d spectra" % (pkt_cnt / PACKETS_PER_SPECTRA)
    print "Dropped %d packets" % missing_packets_count
    print "Wrote zeros for %d straggling packets to end on a complete spectra" % straggling_packets
    fh.close()
