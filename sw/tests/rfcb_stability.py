import telnetlib
import ata_control
import time
import pickle
import pylab

# Ethernet / GPIB dongle address
HOST = "10.10.1.199"
PORT = 1234

# Antenna to test
ANTS = ["2a"]
POL = "x"

NSCANS = 300
ATTEN = 15


tn = telnetlib.Telnet(HOST,PORT)

def newSpec(channel):
    tn.write('TRAC:DATA? TRACE1\n')
    spec = tn.read_until('\n')
    spec_list = spec.split(',')
    spec_list =[float(i) for i in spec_list]
    return spec_list

for ANTN, ANT in enumerate(ANTS):
    ata_control.set_rf_switch(0, ANTN+1)
    output_file = "stability_test_%s_%s_%d.pkl" % (ANT, POL, time.time())
    spec_out = []
    stats_out = []
    for atten in range(NSCANS):
        ata_control.set_pam_atten(ANT, POL, ATTEN) 
        time.sleep(1)
        stats_out += [ata_control.get_pam_status(ANT)]
        spec_out += [newSpec(1)]
        time.sleep(2)
    
    with open(output_file, "w") as fh:
        pickle.dump({'stats':stats_out, 'spec':spec_out}, fh)

