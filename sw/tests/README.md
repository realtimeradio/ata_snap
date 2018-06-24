# Linearity Tests

`rfcb_linearity.py` is a test script that sweeps the PAX attenuator settings for
a series of antennas while capturing the PAX detector readings, and a post-RFCB
spectrum from a spectrum analyser. Data are dumped to pickle files.

These files can be plotted with `plot_rfcb_linearity.py`

Data from a scan of 3C196 at 3000 MHz and 6000 MHz tunings can be found in
`linearity_test_3000mhz_3c196` and `linearity_test_6000mhz_3c196`, respectively

## Complete antenna PAX attenuation vs det readings
A complete sweep of all PAX attenuations and their corresponding det_x / det_y
values was collected by JR on the morning of 23 June 2018, and can be found in db_pams_dets.json

These can be plotted with `plot_attn_vs_dets.py`

# Stability Tests
