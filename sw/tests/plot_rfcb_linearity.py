import pickle
from matplotlib import pyplot as plt
import numpy as np
import sys

def get_fit(att, power, lowoffset=7, highoffset=7):
    max_pow = power.max()
    min_pow = power.min()
    #print min_pow, max_pow
    mask = (power<(max_pow - highoffset)) & (power>(min_pow + lowoffset))
    #print mask
    if np.all(~mask):
        mask = ~mask
    pow_in_range = power[mask]
    att_in_range = att[mask]
    #print att_in_range, pow_in_range
    #pow_in_range = power[5:-5]
    #att_in_range = att[5:-5]
    lin_fit_params = np.polyfit(att_in_range, pow_in_range, 1)
    lin_fit = np.polyval(lin_fit_params, att)
    return lin_fit

def get_compression_point(att, fit, data, v=1):
    try:
        att = np.array(att, dtype=np.float32)
        diff = fit - data
        compression_point = att[diff>v][-1]
        compression = diff[diff>v][-1]
        compression_point_interp = np.interp(1.0, diff[len(diff[diff>v])-1:len(diff[diff>v])+1][::-1], att[len(diff[diff>v])-1:len(diff[diff>v])+1][::-1])
        #print diff[len(diff[diff>v])-1:len(diff[diff>v])+1], att[len(diff[diff>v])-1:len(diff[diff>v])+1]
    except:
        compression = -1
        compression_point = -1
    return compression_point, compression, compression_point_interp



# Prep plots
fig0, ax0 = plt.subplots(1,1)
fig1, ax1 = plt.subplots(1,1)
fig2, ax2 = plt.subplots(1,1)
fig3, ax3 = plt.subplots(1,1)
ax2.set_xlabel("PAM Attenuation [dB]")

for filename in sys.argv[1:]:
    with open(filename, "r") as fh:
        #print "Opening %s" % filename
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
    if pol == 'x':
        att = att_x
    else:
        att = att_y
    spec = np.array(p['spec'])[:,400:800]
    lin_powers = (10**(spec/10.)).sum(axis=1)
    db_powers = 10*np.log10(lin_powers)
    fit = get_fit(att, db_powers)
    data_line = ax2.plot(att, db_powers, label="%s-%s" % (ant,pol))
    color = data_line[0].get_color()
    fit_line = ax2.plot(att, fit, "--")
    fit_line[0].set_color(color)
    comp_point, comp, comp_point_interp = get_compression_point(att, fit, db_powers)
    print "Ant %s-%s has %.2f dB compression at attenuation of %d dB (interpolated %.2f)" % (ant, pol, comp, comp_point, comp_point_interp)
    
    for s in spec:
        ax0.plot(s)
    ax0.set_xlabel("Spectral Channel")
    ax0.set_ylabel("Power (dB arb. ref.)")
    
    ax1.plot(lin_powers / lin_powers.mean(), label=ant)
    ax1.legend(loc="best")
    ax1.set_xlabel("Integrations")
    ax1.set_ylabel("Total RFCB Power (dB)")

ax2.legend(loc="best")
ax2.set_ylabel("Power [dB (arb reference)]")

plt.show()
