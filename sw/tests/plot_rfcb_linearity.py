import pickle
from matplotlib import pyplot as plt
import numpy as np
import sys

# Prep 3 plots
fig0, ax0 = plt.subplots(1,1)
fig1, ax1 = plt.subplots(1,1)

for filename in sys.argv[1:]:
    with open(filename, "r") as fh:
        print "Opening %s" % filename
        p = pickle.load(fh)
    
    if "_y_" in filename:
        pol = "y"
    elif "_x_" in filename:
        pol = "x"
    else:
        print "What polarization is this?! Neither _x_ nor _y_ are in the filename!"
        exit()
    ant = p['stats'][0]['ant']
    det_x = np.array([t['det_x'] for t in p['stats']])
    det_y = np.array([t['det_y'] for t in p['stats']])
    att_xf = np.array([t['atten_xf'] for t in p['stats']])
    att_xb = np.array([t['atten_xb'] for t in p['stats']])
    att_x = att_xf + att_xb
    att_yf = np.array([t['atten_yf'] for t in p['stats']])
    att_yb = np.array([t['atten_yb'] for t in p['stats']])
    att_y = att_yf + att_yb
    spec = np.array(p['spec'])[:,400:800]
    powers = (10**(spec/10.)).sum(axis=1)
    
    for s in spec:
        ax0.plot(s)
    ax0.set_xlabel("Spectral Channel")
    ax0.set_ylabel("Power (dB arb. ref.)")
    
    ax1.plot(powers / powers.mean(), label=ant)
    ax1.legend(loc="best")
    ax1.set_xlabel("Integrations")
    ax1.set_ylabel("Total RFCB Power (dB)")

plt.show()
