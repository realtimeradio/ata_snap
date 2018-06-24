"""
Python wrappers for various command line
tools at the ATA.
NB: many of these can only be run on
`nsg-work1`, which has control of the USB
switches and attenuators in the ATA test
setup.
"""

from subprocess import Popen, PIPE
import socket
RF_SWITCH_HOST = "nsg-work1"
ATTEN_HOST = "nsg-work1"

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

def write_obs_to_db(source, freq, az_offset=0.0, el_offset=0.0, ants=["dummy"]):
    """
    Write details of an observation in to the observation database.
    """
    proc = Popen(["obs2db", ",".join(ants), "%f" % freq, source, "%f" % az_offset, "%f" % el_offset])
    proc.wait()

def end_obs():
    """
    Write the current time as the end of the latest observation in the obs database.
    """
    proc = Popen(["obs2db", "stop"])
    proc.wait()

def get_latest_obs():
    """
    Get the latest observation ID from the obs database.
    """
    proc = Popen(["obsgetid"], stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    return int(stdout)

def point(source, freq, az_offset=0.0, el_offset=0.0, ants=['dummy'], writetodb=True):
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
    if socket.gethostname == RF_SWITCH_HOST:
        proc = Popen(["sudo", "rfswitch", "%d" % sel, "%d" % switch], stdout=PIPE, stderr=PIPE)
    else:
        proc = Popen(["ssh", "sonata@%s" % RF_SWITCH_HOST, "sudo", "rfswitch", "%d" % sel, "%d" % switch], stdout=PIPE, stderr=PIPE)
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
    if socket.gethostname == ATTEN_HOST:
        proc = Popen(["sudo", "atten", "%.2f" % val, "%d" % switch],  stdout=PIPE, stderr=PIPE)
    else:
        proc = Popen(["ssh", "sonata@%s" % ATTEN_HOST, "sudo", "atten", "%.2f" % val, "%d" % switch],  stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    if stderr.startswith("OK"):
        return
    else:
        raise RuntimeError("Set attenuation 'sudo atten %.2f %d' failed!" % (val, switch))

def set_pam_atten(ant, pol, val):
    """
    Set the attenuation of antenna `ant`, polarization `pol` to `val` dB
    """
    proc = Popen(["ssh", "obs@tumulus", "atasetpams", ant, "-%s"%pol, "%f"%val])
    proc.wait()

def get_pam_status(ant):
    """
    Get the PAM attenuation settings and power detector readings for antenna `ant`
    """
    proc = Popen(["getdetpams", ant],  stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    x = stdout.split(',')
    return {'ant':x[0], 'atten_xf':float(x[1]), 'atten_xb':float(x[2]), 'atten_yf':float(x[3]), 'atten_yb':float(x[4]), 'det_x':float(x[5]), 'det_y':float(x[6])}

def reserve_antennas(ants=["1f", "2a", "2b", "2e", "3l", "4g", "4l", "5c"]):
    """
    Set antennas `ants` (which should be a list of strings, eg ["1f", "2a"])
    to antgroup bfa.
    """
    proc = Popen(["antreserve", "none", "bfa"] + ants, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    lines = stdout.split('\n')
    for line in lines:
        cols = line.split()
        if (len(cols) > 0) and (cols[0]  == "bfa"):
            bfa = cols[1:]
    for ant in ants:
        if ant not in bfa:
            print nonegroup
            print ants
            raise RuntimeError("Failed to move antenna %s to antgroup bfa" % ant)

def release_antennas(ants=["1f", "2a", "2b", "2e", "3l", "4g", "4l", "5c"]):
    """
    Set antennas `ants` (which should be a list of strings, eg ["1f", "2a"])
    to antgroup none.
    """
    proc = Popen(["antreserve", "bfa", "none"] + ants, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    lines = stdout.split('\n')
    for line in lines:
        cols = line.split()
        if (len(cols) > 0) and (cols[0]  == "none"):
            nonegroup = cols[1:]
    for ant in ants:
        if ant not in nonegroup:
            print nonegroup
            print ants
            raise RuntimeError("Failed to move antenna %s to antgroup none" % ant)

def get_ra_dec(source, deg=True):
    """
    Get the J2000 RA / DEC of `source`. Return in decimal degrees (DEC) and hours (RA)
    by default, unless `deg`=False, in which case return in sexagesimal.
    """
    proc = Popen(["atacheck", source], stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    for line in stdout.split("\n"):
        if "Found %s" % source in line:
            cols = line.split()
            ra  = float(cols[-1].split(',')[-2])
            dec = float(cols[-1].split(',')[-1])
    if deg:
        return ra, dec
    else:
        ram = (ra % 1) * 60
        ras = (ram % 1) * 60
        ra_sg = "%d:%d:%.4f" % (int(ra), int(ram), ras)
        decm = (dec % 1) * 60
        decs = (decm % 1) * 60
        dec_sg = "%d:%d:%.4f" % (int(dec), int(decm), decs)
        return ra_sg, dec_sg

