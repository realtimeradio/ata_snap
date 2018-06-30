import socket
import numpy as np
import time
import sys
import os
import argparse
from ata_snap import ata_control
from subprocess import Popen

def unpack(pkt):
    header = np.fromstring(pkt[0:8], dtype=">L")
    d = np.fromstring(pkt[8:], dtype=">i")
    xx = d[2::4]
    yy = d[3::4]
    #xy_r = d[3::4]
    #xy_i = d[4::4]
    return header, xx, yy

parser = argparse.ArgumentParser(description='Start a process to write 10GbE SNAP data to disk',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('filename', type=str,
                    help = 'filename to write to (timestamp will be appended')
parser.add_argument('inttime', type=float,
                    help = 'Number of seconds to record for')
parser.add_argument('--makefb', dest='makefb', action='store_true', default=False,
                    help ='Use this flag to add filterbank headers to raw files')
parser.add_argument('-s', dest='source', type=str, default="psrb0329+54",
                    help ='Source name (as per ATA catalog calls)')
parser.add_argument('-a', dest='acc_len', type=int, default=1024,
                    help ='Accumulation length, in spectra')
parser.add_argument('-f', dest='srate', type=float, default=838.8608,
                    help ='Accumulation length, in spectra')
parser.add_argument('-r', dest='rfc', type=float, default=3500.0,
                    help ='RF centre frequency in MHz')
parser.add_argument('-i', dest='ifc', type=float, default=629.1452,
                    help ='IF centre frequency in MHz')


args = parser.parse_args()

PORT = 10000
IP = "10.10.10.131"
PACKETS_PER_SPECTRA = 4
PRINT_PACKETS = 4000
N_CHANNELS = 2048
N_STOKES_PER_PACKET = 4
BYTES_PER_WORD = 4
HEADER_BYTES = 8

bytes_per_packet = BYTES_PER_WORD * N_CHANNELS * N_STOKES_PER_PACKET / PACKETS_PER_SPECTRA + HEADER_BYTES
print "Bytes per packet: %d" % bytes_per_packet

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((IP, PORT))

starttime = time.time()
fh = open("%s_%d.raw" % (args.filename, starttime), "w")
fh_fullname = fh.name
fh_basename = os.path.basename(fh_fullname)

pkt_cnt = 0
missing_packets_count = 0
wait = True
try:
    tick = time.time()
    while(True):
        data = sock.recv(bytes_per_packet)
        h, xx, yy = unpack(data)
        if wait:
            if h % PACKETS_PER_SPECTRA == 0:
                wait = False
            else:
                continue
        if pkt_cnt != 0:
            if h != last_h + 1:
                missing_packets = h - last_h - 1
                missing_packets_count += missing_packets
                print "%d PACKETS LOST! (running total: %d)" % (missing_packets, missing_packets_count)
                padding = np.zeros(missing_packets * N_CHANNELS / PACKETS_PER_SPECTRA, dtype=np.float32).tostring()
                fh.write(padding)
                pkt_cnt += missing_packets
        last_h = h
        #I = (np.array(xx, dtype=np.float32) + np.array(yy, dtype=np.float32)).tostring()
        I = np.array(xx, dtype=np.float32).tostring()
        pkt_cnt += 1
        if pkt_cnt % PRINT_PACKETS == 0:
            tock = time.time()
            n_spectra = pkt_cnt / PACKETS_PER_SPECTRA
            print "Received packet %d (spectra %d) (last %d spectra took %.1f seconds)" % (pkt_cnt, n_spectra, PRINT_PACKETS / PACKETS_PER_SPECTRA, tock-tick)
            tick = tock
        fh.write(I)
        if time.time() > (starttime + args.inttime):
            break
except KeyboardInterrupt:
    pass

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

# Finally make the filterbank header
if args.makefb:
    print "Making filterbank header"
    ra, dec = ata_control.get_ra_dec(args.source, deg=False)
    fbhdr_filename = fh_fullname + ".fbhdr"
    fb_args = [
      "-o", fbhdr_filename,
      "-nifs", "1",
      "-fch1", "%8f" % (args.rfc - args.srate + args.ifc),
      "-source", args.source.strip("psr").upper(),
      "-filename", fh_basename,
      "-telescope", "ATA",
      "-src_raj", ra.replace(":",""),
      "-src_dej", dec.replace(":",""),
      "-tsamp", "%.8f" % (args.acc_len * N_CHANNELS * 2 / args.srate), # outputs micrpsecs for srate in MHz
      "-foff", "%.8f" % (args.srate / 2 / N_CHANNELS), # in MHz for srate in MHz
      "-nbits", "32",
      "-nchans", "%d" % N_CHANNELS,
      "-tstart", "%.8f" % (starttime / 86400. + 40587),
    ]
    proc = Popen(["filterbank_mkheader"] + fb_args)
    proc.wait()

    print "Reading header file"
    with open(fh_fullname, "rb") as fh:
        data = fh.read()
    print "Reading data file"
    with open(fbhdr_filename, "rb") as fh:
        header = fh.read()
    print "Writing filterbank file"
    with open(fh_fullname + ".fil", "wb") as fh:
        fh.write(header + data)
