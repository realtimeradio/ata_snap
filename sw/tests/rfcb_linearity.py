import telnetlib
import ata_control
import time
import pickle
import pylab

# Ethernet / GPIB dongle address
HOST = "10.10.1.199"
PORT = 1234

# Antenna to test
ANTS = ["2a", "2b", "2e", "3l", "1f", "5c", "4k", "4g"]
POL = "x"

SCAN_MIN = 0
SCAN_MAX = 60
SCAN_STEP = 2


tn = telnetlib.Telnet(HOST,PORT)

def newSpec(channel):
    tn.write('TRAC:DATA? TRACE1\n')
    spec = tn.read_until('\n')
    spec_list = spec.split(',')
    spec_list =[float(i) for i in spec_list]
    return spec_list

for ANTN, ANT in enumerate(ANTS):
    ata_control.set_rf_switch(0, ANTN+1)
    output_file = "linearity_test_%s_%s_%d.pkl" % (ANT, POL, time.time())
    spec_out = []
    stats_out = []
    for atten in range(SCAN_MIN, SCAN_MAX, SCAN_STEP):
        ata_control.set_pam_atten(ANT, POL, atten)
        time.sleep(1)
        stats_out += [ata_control.get_pam_status(ANT)]
        spec_out += [newSpec(1)]
        time.sleep(2)
    
    with open(output_file, "w") as fh:
        pickle.dump({'stats':stats_out, 'spec':spec_out}, fh)

