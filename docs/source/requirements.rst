Specifications
==============

Requirements
------------

ADC Sample Rate
~~~~~~~~~~~~~~~

The F-Engine firmware shall pass timing analysis for a maximum ADC sample rate of 2048 Msps.

Frequency Channels
~~~~~~~~~~~~~~~~~~

The F-Engine firmware shall internally generate 4096 complex-valued frequency channels over the digitized Nyquist band.
For an ADC sample rate of 2048 Msps, this represents a channel bandwidth of 250 kHz.
Channels shall be generated using an 8-tap PFB frontend.

Input Coarse Delay
~~~~~~~~~~~~~~~~~~

The F-engine design shall provision for a runtime programmable coarse (1 ADC sample precision) delay, individually set for each analog input.
The maximum depth of this delay shall be at least 8192 ADC samples (4096 ns at 2048 Msps sample rate)

Output Bandwidth
~~~~~~~~~~~~~~~~

The F-engine design shall be capable of outputting 4096 frequency channels at 4+4 bit complex resolution per sample, or at least 2048 frequency channels of bandwidth with 8+8 bit complex resolution.
At 2048 Msps sampling clock, this corresponds to 1024 MHz bandwidth at 4+4 bits resolution, or 512 MHz bandwidth at 8+8 bits resolution.

Output is via UDP packet streams over a pair of 10Gb/s Ethernet interfaces.

Output Format
~~~~~~~~~~~~~

Data shall be output using Ethernet jumbo frames.
Data payloads shall group multiple polarizations, frequency channels, and time samples in each packet ordered (fastest to slowest axis) as ``polarization x freq. channel x time sample``

A variety of outputs with different numbers of samples, and frequency channels gathered in each packet shall be provided.

  1. 16 times, 256 channels, 2 polarizations, 4+4 bit (8kB packets; 16 packets / 4096 channels)
  2. 16 times, 128 channels, 2 polarizations, 4+4 bit (4kB packets; 32 packets / 4096 channels)
  3. 16 times, 128 channels, 2 polarizations, 8+8 bit (8kB packets; 16 packets / 2048 channels)
  4. 16 times, 64  channels, 2 polarizations, 4+4 bit (4kB packets; 32 packets / 2048 channels)

Specification
-------------

ADC Sample Rate
~~~~~~~~~~~~~~~

The F-Engine design meets timing at a sample rate of 2048 Msps (FPGA DSP pipeline clock rate of 256 MHz)

Frequency Channels
~~~~~~~~~~~~~~~~~~

The F-engine firmware generates 4096 complex-valued frequency channels using an 8-tap PFB with a 25-bit precision FFT.
This FFT has sufficient dynamic range to negate the need for FFT shfit control.

Scaling coefficients are provided with a dynamic range exceeding that of the FFT. Any FFT output power can be effectively converted to either 4- or 8-bit data.

Input Coarse Delay
~~~~~~~~~~~~~~~~~~

The F-engine design provides per-input programmable delay of up to 16384 ADC samples

Output Bandwidth
~~~~~~~~~~~~~~~~

The F-engine design can output all 4096 channels at 4+4 bit resolution.

The F-engine design can output up to 2304 (576 MHz bandwidth with a 2048 Msps sample clock) at 8+8 bit resolution using 128 channels per packet.

The F-engine design can output up to 2432 (608 MHz bandwidth with a 2048 Msps sample clock) at 8+8 bit resolution using 64 channels per packet.

Output is via UDP packet streams over a pair of 10Gb/s Ethernet interfaces, with each interface providing a different subset of the total bandwidth.

The start point of the transmitted block of channels can be placed arbitrarily with a precision of 8 channels.

Output Format
~~~~~~~~~~~~~

Data packets can be constructed with payloads either in (fastest to slowest axis) ``polarization x freq. channel x time sample`` or ``polarization x time sample x freq channel`` order.

Data payloads can be constructed with 16 time samples per packet, and any multiple of 8 (4+4 bit mode) or 4 (8+8 bit mode) frequency channels.

Any total number of frequency channels may be transmitted, subject to these restriction, and the total Ethernet bandwidth available.

Each data packet has an application header of 16 bytes. Total protocol overhead (including this application header) is 70 bytes per packet (<2% for 4kB packets).
