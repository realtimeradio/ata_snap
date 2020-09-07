# Firmware Overview
This repository contains SNAP firmware and associated control software originally designed for use at the Allen Telescope Array.

The current firmware model is `snap_adc5g_feng[_rpi].slx`.

It has the following features:

* Dual-polarization input
* Up to 2500 MSamples/s 8-bit sampling using CASPER's `adc5g` ADC card
* 4096 Frequency Channels (8-tap FIR + FFT architecture)
