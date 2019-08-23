import json
import numpy as np
import pylab

with open("db_pams_dets.json", "r") as fh:
    ants = json.load(fh)['values']

for ant, val in ants.iteritems():
    ab = np.array(val['pamx_back'])
    af = np.array(val['pamx_front'])
    at = ab + af
    dx = np.array(val['detx'])
    pylab.plot(at, 10*np.log10(dx), label=ant)

pylab.xlabel("PAM attenuation setting (dB)")
pylab.ylabel("10log10(detx reading)")
pylab.legend()

pylab.show()
