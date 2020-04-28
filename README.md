# ata_snap
This repository contains SNAP firmware and associated control software originally designed for use at the Allen Telescope Array.

The current firmware model is `snap_adc5g_feng.slx`.

It has the following features:

* Dual-polarization input
* Up to 1250 MSamples/s 8-bit sampling using CASPER's `adc5g` ADC card
* 4096 Frequency Channels (8-tap FIR + FFT architecture)

Spectrometer output mode
* XX, YY, XY output products
* Slow-speed polled output @ ~1 second time resolution
* 10 Gb Ethernet output @ ~100 microsecond time resolution

Voltage "F-Engine" mode
* 4+4 bit complex channelized voltages (4096 channels over the Nyquist band)
* 10 Gb Ethernet output (only available when not using the spectrometer 10 GbE output)
* Output up to 2048 of 4096 channels
* 8192 Byte (+ 64 byte header) UDP jumbo packets
* Spread 2048 channels over up to 8 different destination IP addresses

## Compiling the firmware

### Software versions
- Ubuntu 18.04
- MATLAB/Simulink 2019a
- Xilinx Vivado System Edition 2019.1.3

### To open/modify/compile:

1. Clone this repository
2. Clone submodules:
  ```
  git submodule init
  git submodule update
  ```
3. Create a local environment specification file `startsg.local`.
4. From the top level of this repository, run `startsg` (if your environment file is called `startsg.local`) or `startsg <my_local_environment_file.local>`.

### Source Files
- `snap_adc5g_feng.slx` -- Simulink firmware model
- sw/ata_snap -- Python control software & supporting libraries

