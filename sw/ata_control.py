"""
Python wrappers for various command line
tools at the ATA.
NB: many of these can only be run on
`nsg-work1`, which has control of the USB
switches and attenuators in the ATA test
setup.
"""

from subprocess import Popen, PIPE

def get_sky_freq():
    """
    Return the sky frequency (in MHz) currently
    tuned to the center of the ATA band
    """
    proc = Popen(["atagetskyfreq", "a"], stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    return float(stdout.strip())

def get_ascii_status():
    """
    Return an ascii table of lots of ATA
    status information.
    """
    proc = Popen("ataasciistatus", stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    return stdout

def point(source, freq, az_offset=0.0, el_offset=0.0):
    """
    Point the ATA at `source`, with an offset
    from the source's position of `az_offset` degrees
    in azimuth and `el_offset` degrees in elevation.
    Tune to a center sky frequency of `freq` MHz
    """
    proc = Popen(["pointshift", source, "%f" % freq, "%f" % az_offset, "%f" % el_offset])
    proc.wait()

def set_rf_switch(switch, sel):
    """
    Set RF switch `switch` (0..1) to connect the COM port
    to port `sel` (1..8)
    """
    proc = Popen(["sudo", "rfswitch", "%d" % sel, "%d" % switch], stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    if stdout.startswith("OK"):
        return
    else:
        raise RuntimeError("Set switch 'sudo rfswitch %d %d' failed!" % (sel, switch))

def set_atten(switch, val):
    """
    Set attenuation of switch `switch` (0..1)
    to `val` dB.
    Allowable values are 0.0 to 31.75
    """
    proc = Popen(["sudo", "atten", "%.2f" % val, "%d" % switch],  stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    if stderr.startswith("OK"):
        return
    else:
        raise RuntimeError("Set attenuation 'sudo atten %.2f %d' failed!" % (val, switch))
