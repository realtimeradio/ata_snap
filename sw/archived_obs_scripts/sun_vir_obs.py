import os
import ata_control
from subprocess import Popen, PIPE

sources = ["vira"]
freqs = range(2000, 3001, 1500)
ants = ['2a', '2b', '2e', '3l', '1f', '5c', '4k', '4g'] # this is wrong -- 4k is really 4L!!!
NINTS = 15
NONOFFS = 4
for source in sources:
    for freq in freqs:
        for antn, ant in enumerate(ants):
            for onoff_n, onoff in enumerate(["on", "off"]*NONOFFS):
                print "Pointing to %s at %.1f MHz" % (source, freq)
                if onoff == "on":
                    print "Observing %s at %.2f MHz with Antenna %s" % (source, freq, ant)
                    ata_control.point(source, freq)
                elif onoff == "off":
                    print "Observing %s at %.2f MHz with Antenna %s (Offset 10)" % (source, freq, ant)
                    ata_control.point(source, freq, 10, 0)
                #os.system("/home/sonata/dev/agilent_sa_gpib/save_spec_automate.py /home/sonata/data/%s_%s_%.2f &" % (source, onoff, freq))
                ata_control.set_rf_switch(0, antn)
                ata_control.set_rf_switch(1, antn)
                proc = Popen(["python", "take_spec_data.py", "snap1", "/home/sonata/dev/ata_snap/snap_adc5g_spec/outputs/snap_adc5g_spec_2018-06-23_1048.fpg", "-n", "%d" % NINTS, "-a", ant, "-c", "%s_%s%d_ant_%s_%.2f" % (source, onoff, onoff_n,  ant, freq)])
                proc.wait()

