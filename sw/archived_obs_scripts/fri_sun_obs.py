import os
import ata_control
from subprocess import Popen, PIPE

sources = ["sun"]
freqs = range(3000, 3001, 1000)
ants = ['1h', '2a', '2b', '2e', '2j', '3d', '3l', '1a']
NINTS = 60
for source in sources:
    for freq in freqs:
        for antn, ant in enumerate(ants):
            for onoff in ["on", "off"]:
                print "Pointing to %s at %.1f MHz" % (source, freq)
                if onoff == "on":
                    ata_control.point(source, freq)
                elif onoff == "off":
                    ata_control.point(source, freq, 10, 0)
                print "Observing %s at %.2f MHz with Antenna %s" % (source, freq, ant)
                #os.system("/home/sonata/dev/agilent_sa_gpib/save_spec_automate.py /home/sonata/data/%s_%s_%.2f &" % (source, onoff, freq))
                ata_control.set_rf_switch(0, antn)
                proc = Popen(["python", "take_spec_data.py", "snap1", "/home/sonata/dev/ata_snap/snap_adc5g_spec/outputs/snap_adc5g_spec_2018-06-16_1616.fpg", "-n", "%d" % NINTS, "--noy", "-c", "%s_%s_ant_%s_%.2f" % (source, onoff, ant, freq)])
                proc.wait()

