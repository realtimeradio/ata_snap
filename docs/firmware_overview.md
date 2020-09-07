# Firmware Overview

The provided firmware implements a 4096-channel polyphase filter banks on each of two independent analog inputs. The pipeline is compiled for a Xilinx XC7k160t-based [SNAP board][https://casper.ssl.berkeley.edu/wiki/SNAP].

The signal processing pipeline takes as input two data streams sampled at up to 2500 Msps with 8 bits resolution. These are provided by the CASPER-designed [ADC5g card][https://casper.ssl.berkeley.edu/wiki/ADC1x5000-8], which interfaces with a SNAP board via a ZDOK connector.

The pipeline -- shown in high-level form below, with processing modules shown in blue and runtime settings shown in yellow circles -- creates two output data products: accumulated spectral power, and channelized voltages. One of these two outputs can be selected for output over a 10GbE link.

![pipeline-image][https://github.com/realtimeradio/ata_snap/blob/voltage-capture/docs/figs/ata-snap-feng.png]

## Channelization
Both processing pipelines share a common polyphase-filterbank channelizer, formed from an FIR filter and subsequent FFT. This channelizer takes real-valued 8-bit voltages as its inputs, and outputs 18 bit complex (i.e. 18-bit real + 18-bit imaginary) spectra with 4096 channels critically sampling the system's Nyquist band. When operated at the maximum ADC sample rate of 2500 Msps, each spectrum comprises 4096 channels each approximately 305 kHz wide.

In the channelization pipeline, all coefficients are stored as 18 bit complex values, normalized to a range of +/-1, and an 18 bit data path is maintained throughout the filter.
A runtime-configurable "shift schedule" is used to optionally enact divide-by-two operations on the data path after each FFT butterfly stage to prevent data overflows. The pipeline shift schedule is user-chosen based on the observed antenna power levels at the start of an observation.

## Spectrometer Pipeline
The Spectrometer pipeline computes the accumulated power of the upstream spectra. First, the auto- and cross-power of the pairs of inputs are computed at full precision. 18-bit voltage inputs are converted into 36-bit unsigned powers (in the autocorrelation case) or 37-bit signed complex cross-powers.

In the accumulation stage of the spectrometer, these powers are scaled down by a factor of 4096 using a round-to-even scheme, and then successive spectra are summed into a 32-bit signed vector accumulator.\
Accumulation length is a runtime-controlled parameter, and data may be streamed out over 10GbE (appropriate for short <<1s accumulation period) or polled via a remote software process.


## Voltage Pipeline

The voltage pipeline performs no averaging, and thus operates at lower bit precision than the spectrometer pipeline in order to fit into a limited (10Gb/s) output bandwidth. In the provided firmware, the voltage pipeline outputs 4 bit complex samples.

Prior to quantization to 4 bits, tuning of signal levels is possible by multiplying each 4096 point, 18 bit, complex FFT spectra with a vector of 16 bit coefficients. Each coefficient has a range of 0-2048, and a resolution of 0.03125. The FPGA design stores independent coefficients for each analog input and each polyphase-filterbank channel.

Following this equalization step, each sample is quantized to 4 bit complex representation, using a round-to-even scheme. Values are saturated at a value of +/- 7, in order to maintain symmetry around zero.

If operated at the maximum supported ADC sample rate of 1250 Msps, the total system bandwidth after 4-bit quantization is 20 Gb/s. In order to maintain a rate less than 10 Gb/s, only a subset of frequency channels are transmitted.


## Test modes & Software Control

The above system block diagram gives an indication of some of the runtime-configurable pipeline settings which are shown in yellow circles. As well as the settings described above, other 
