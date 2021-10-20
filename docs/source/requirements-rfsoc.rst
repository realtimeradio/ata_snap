RFSoC Firmware Specifications
=============================

Requirements
------------

Inputs
~~~~~~

The F-engine firmware shall channelize 16 independent ADC streams (assumed to be
8 independent, dual-polarization ATA IFs).

ADC Sample Rate
~~~~~~~~~~~~~~~

The F-Engine firmware shall pass timing analysis for a maximum ADC sample rate of 2048 Msps.

Frequency Channels
~~~~~~~~~~~~~~~~~~

The F-Engine firmware shall internally generate at least 1024 complex-valued frequency channels over the digitized Nyquist band.
For an ADC sample rate of 2048 Msps, this represents a channel bandwidth of at least 1 MHz.
Channels shall be generated using an 4-tap PFB frontend.

Input Coarse Delay
~~~~~~~~~~~~~~~~~~

The F-engine design shall provision for a runtime programmable coarse (1 ADC sample precision) delay, individually set for each analog input.
The maximum depth of this delay shall be at least 8192 ADC samples (4096 ns at 2048 Msps sample rate)

Output Bandwidth
~~~~~~~~~~~~~~~~

The F-engine design shall be capable of outputting at least 672 MHz of bandwidth, at 8+8 bit complex resolution per sample.

Output is via UDP packet streams over a pair of 100Gb/s Ethernet interfaces.

Output Format
~~~~~~~~~~~~~

Data shall be output using Ethernet jumbo frames.
Data payloads shall group pairs of polarizations, multiple frequency channels, and multiple time samples in each packet ordered (fastest to slowest axis) as ``polarization x time sample x freq. channel``

A variety of outputs with different numbers of frequency channels gathered in each packet shall be provided, eg.

  1. 16 times, 96 channels, 2 polarizations, 8+8 bit (6144B packets; 14 packets / 1344 channels)
  2. 16 times, 128 channels, 2 polarizations, 8+8 bit (8kB packets; 8 packets / 1024 channels)

Specification
-------------

ADC Sample Rate
~~~~~~~~~~~~~~~

The F-Engine design meets timing at a sample rate of 2048 Msps (FPGA DSP pipeline clock rate of 256 MHz)

Frequency Channels
~~~~~~~~~~~~~~~~~~

The F-engine firmware generates 2048 complex-valued frequency channels using a 4-tap PFB with a 25-bit precision FFT.
This FFT has sufficient dynamic range to negate the need for FFT shift control.

Scaling coefficients are provided with a dynamic range exceeding that of the FFT. Any FFT output power can be effectively converted to 8-bit data.

Input Coarse Delay
~~~~~~~~~~~~~~~~~~

The F-engine design provides per-input programmable delay of up to 8192 ADC samples

Output Bandwidth
~~~~~~~~~~~~~~~~

The F-engine design can output at least 1344 channels at 8+8 bit resolution.

The start point of the transmitted block of channels can be placed arbitrarily with a precision of 32 channels. 

Output Format
~~~~~~~~~~~~~

Data packets can be constructed with payloads in (fastest to slowest axis)  ``polarization x time sample x freq channel`` order.

Data payloads are constructed with 16 time samples per packet, and any multiple of 32 frequency channels, subject to the total Ethernet bandwidth available, and a maximum Ethernet MTU of 9000 Bytes.

Invidiual packets may be assigned independent destination IP addresses and UDP ports.

Each data packet has an application header of 16 bytes. Total protocol overhead (including this application header) is 70 bytes per packet (<2% for 4kB packets).
