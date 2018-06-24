from subprocess import Popen, PIPE
import os
sources = ["3C295"]
freqs = range(1000, 10001, 1000)
ants = ['1e','1h','1k','2a','2b','2e','2h','2j','2m','3d','3l','4j']
NINTS = 180
for source in sources:
    for freq in freqs:
        for onoff in ["on", "off"]:
            if onoff == "on":
                proc = Popen(["pointshift", source, "%f" % freq, "0", "0"])
            elif onoff == "off":
                proc = Popen(["pointshift", source, "%f" % freq, "0", "10"])
            proc.wait()
            stdout, stderr = proc.communicate()
            for antn, ant in enumerate(ants):
                print "Observing %s at %.2f MHz with Antenna %s" % (source, freq, ant)
                os.system("/home/sonata/dev/agilent_sa_gpib/save_spec_automate.py /home/sonata/data/%s_%s_ant_%s_%.2f &" % (source, onoff, ant, freq))
                proc = Popen(["sudo", "rfswitch", "%d" % (antn+1), "0"])
                proc.wait()
                proc = Popen(["python", "take_spec_data.py", "snap1", "/home/sonata/dev/ata_snap/snap_adc5g_spec/outputs/snap_adc5g_spec_2018-06-16_1616.fpg", "-n", "%d" % NINTS, "-c", "%s_%s_ant_%s_%.2f" % (source, onoff, ant, freq)])
                proc.wait()

