.. |version| replace:: 2.1.0

ATA RFSoC F-Engine Firmware User Manual
=======================================
..
  As part of the Allen Telescope Array (ATA) refurbishment project, the digitization and channelization hardware used at the ATA has been upgraded to use the Xilinx Kintex 7 ``SNAP'' platform. Each SNAP board provides more processing power than the iBoB platform it replaces, and potentially allows wider bandwidth processing. This document describes the functionality of the SNAP F-Engine hardware and firmware, including its user interface and run-time parameters.


Introduction
------------
This repository contains software for an RFSoC-based F-Engine (i.e. channelizer) system for the Allen Telescope Array (ATA). Corresponding firmware can be found `on github <https://github.com/realtimeradio/ata_rfsoc/blob/main/zrf_volt_8ant_8bit.slx>`_.

The system digitizes sets of 16 RF signals from the ATA at a speed, :math:`f_s`, of up to 2048 Msps and generates 2048 frequency channels over the Nyquist band.

This document described 8-bit *Voltage* mode firmware. (*Spectrometer* mode, and 4-bit *Voltage* mode implementations have also been created, though these are not described here)


This Document
~~~~~~~~~~~~~

This document describes the hardware configuration required by the F-Engine system, the runtime configuration proceedures, and the software control functionality made available to the user.
It also provides a description of the output data formats of each of the two data processing modes.

Nomenclature
------------

Data Types
~~~~~~~~~~

Throughout this document, data types are labelled in diagrams using the nomenclature :math:`X.Y\mathrm{b}`. Unless otherwise stated, this indicates an :math:`X`-bit signed, fixed-point number, with :math:`Y` bits below the binary point.

Where this document indicates an :math:`N`-bit complex number, this implies a :math:`2N`-bit value  with an :math:`N`-bit real part in its most-significant bits, and an :math:`N`-bit imaginary part in its least-significant bits.

.. _sec-data-format:

Output Data Formats
-------------------

Voltage Packets
~~~~~~~~~~~~~~~

The *Voltage* mode of the RFSoC firmware outputs a continuous stream of voltage data, encapsulated in UDP packets.
The format used is common between SNAP and RFSoC ATA backends.
Each packet contains a data payload of up to 8192 bytes, made up of 16 time samples for up to 256 frequency channels of dual-polarization data:

.. code-block:: C

  #define N_t 16
  #define N_p 2

  struct voltage_packet {
    uint8_t version;
    uint8_t type;
    uint16_t n_chans;
    uint16_t chan;
    uint16_t feng_id
    uint64_t timestamp;
    complex8 data[n_chans, N_t, N_p] // 8-bit real + 8-bit imaginary
  };

The header entries are all encoded network-endian and should be interpretted as follows:
  - ``version``; *Firmware version*: Bit [7] is always 1 for *Voltage* packets. The remaining bits contain a compile-time defined firmware version, represented in the form bit[6].bits[5:3].bits[2:0]. This document refers to firmware version |version|.
  - ``type``; *Packet type*: Bit [0] is 1 if the axes of data payload are in order [slowest to fastest] channel x time x polarization. This is currently the only supported mode. Bit [1] is 1 if the data payload comprises 8+8 bit complex integers. This is currently the only supported mode.
  - ``n_chans``; *Number of Channels*: Indicates the number of frequency channels present in the payload of this data packet.
  - ``chan``; *Channel number*: The index of the first channel present in this packet. For example, a channel number ``c`` implies the packet contains channels ``c`` to ``c + n_chans - 1``.
  - ``feng_id``; *Antenna ID*: A runtime configurable ID which uniquely associates a packet with a particular SNAP board.
  - ``timestamp``; *Sample number*: The index of the first time sample present in this packet. For example, a sample number :math:`s` implies the packet contains samples :math:`s` to :math:`s+15`. Sample number can be referred to GPS time through knowledge of the system sampling rate and accumulation length parameters, and the system was last synchronized. See `sec-timing`.

The data payload in each packet is determined by the number of frequency channels it contains.
The maximum is 8192 bytes.
If ``type & 2 == 1`` each byte of data should be interpretted as an 8-bit complex number (i.e. 8-bit real, 8-bit imaginary) with the most significant 8 bits of each byte representing the real part of the complex sample in signed 2's complement format, and the least significant 8 bits representing the imaginary part of the complex sample in 2's complement format.

If ``type & 1 == 1`` the complete payload is an array with dimensions ``channel x time x polarization``, with

  - ``channel`` index running from 0 to ``n_chans - 1``
  - ``time`` index running from 0 to 15
  - ``polarization`` index running from 0 to 1 with index 0 representing the X-polarization, and index 1 the Y-polarization.


Firmware Overview
-----------------

The firmware described in this document is designed in Mathwork's Simulink using CASPERs FPGA programming libraries.
The Simulink source file is available `on github <https://github.com/realtimeradio/ata_rfsoc/blob/main/zrf_volt_8ant_8bit.slx>`_.

Building the Simulink Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The SNAP firmware model (``zrf_volt_8ant_8bit.slx``)  was built with the following software stack.
Use other versions at your peril.

  - Ubuntu 18.04 64-bit
  - MATLAB/Simulink 2019a, including Fixed Point Designer Toolbox
  - Xilinx Vivado System Edition 2020.2.1
  - ``mlib_devel`` (version controlled within the ``ata_rfsoc`` repository.

To obtain and open the Simulink model:

.. code-block:: console

  # Clone the firmware repository
  git clone https://github.com/realtimeradio/ata_rfsoc

  # Clone relevant sub-repositories
  cd ata_rfsoc
  git submodule init
  git submodule update

  # Install the mlib_devel dependencies
  # You may want to install these in a Python virtual environment
  cd mlib_devel
  pip install -r requirements.txt

Next, create a local environment specification file in the ``ata_rfsoc`` directory, named ``startsg.local``.
An example environment file is:

.. code-block:: console

  #!/bin/bash
  ####### User to edit these accordingly ######
  export XILINX_PATH=/data/Xilinx/Vivado/2020.1
  export MATLAB_PATH=/data/MATLAB/R2019a
  # PLATFORM lin64 means 64-bit Linux
  export PLATFORM=lin64
  # Location of your Xilinx license
  export XILINXD_LICENSE_FILE=/home/jackh/.Xilinx/Xilinx.lic
  
  # Library tweaks
  export LD_PRELOAD=${LD_PRELOAD}:"/usr/lib/x86_64-linux-gnu/libexpat.so"
  # An optional python virtual environment to activate on start
  export CASPER_PYTHON_VENV_ON_START=/home/jackh/casper-python3-venv

You should edit the paths accordingly.

To open the firmware model, from the top-level of the repository (i.e. the ``ata_rfsoc`` directory) run ``./startsg``.
This will open MATLAB with appropriate libraries, at which point you can open the ``zrf_volt_8ant_8bit.slx`` Simulink model.
  
Firmware Overview
~~~~~~~~~~~~~~~~~

A pictorial representation of the RFSoC firmware with  annotated data path bit widths is shown in :numref:`fig-ata-rfsoc-feng-8bit`.

.. figure:: _static/figs/ata-rfsoc-feng-volt-8bit.png
    :align: center
    :name: fig-ata-rfsoc-feng-8bit
    
    A pictorial representation of the RFSoC firmware, showing major processing modules and the bit widths of their data paths. Yellow circles in this diagram represent the runtime-controllable elements of the pipeline.

In the remainder of this section an overview of the functional modules in the system is given.

Module Descriptions
~~~~~~~~~~~~~~~~~~~

Here basic explanations of the functionality of the different firmware processing modules is given.
Where modules can be controlled or monitored at runtime, software routines to do so are described in :ref:`sec-runtime-control`.

Delay
^^^^^

The Delay module allows individual RFSoC inputs to be delayed by an integer number of ADC samples.

Timing
^^^^^^

The Timing module allows multiple SNAP boards to be synchronized, and locks data timestamps to a known UTC origin.
Mulitple board synchronization relies on each SNAP board being fed a time-aligned, distributed pulse, with an edge rate of << 1ms.
Alignment of timestamps to UTC requires that the SNAP pulses have a positive edge aligned with a UTC second.

Typically, both of the above requirements can be met by using a syncronization signal which is a distributed GPS-locked Pulse-Per-Second (PPS).

Quality of board synchronization is determined by the nature of the PPS distribution system. For commercial PPS distribution equipment, using length-matched cables, synchronization will be within :math:`<10` ADC samples.

The synchronization process is as follows:

1. Wait for a PPS to pass
2. Arm all SNAP boards in the system to trigger on the next PPS edge
3. Reset on-board spectra counters on the next PPS edge

Relevant Software Methods
`````````````````````````

  - ``sync_wait_for_pps``: Wait for an external PPS pulse to pass
  - ``sync_arm``: Arm the firmware such that the next PPS results in a reset of local counters
  - ``sync_get_last_sync_time``: Return the time that the firmware was last synchronized to a PPS pulse
  - ``sync_get_ext_count``: Return the number of PPS pulses returned since the FPGA was last programmed
  - ``sync_get_fpga_clk_pps_interval``: Return the number of FPGA clock ticks between the last two PPS pulses
  - ``sync_get_adc_clk_freq``: Infer the ADC clock rate from the number of FPGA clock ticks between PPS pulses


Filter Bank
^^^^^^^^^^^

The Filter Bank (aka Polyphase Filter Bank, PFB [pfb]_) separates the X- and Y-polarization input broad-band data streams into 2048 frequency channels, starting at DC, with centers separated by :math:`\frac{f_s}{4096}`.
These baseband frequencies, from DC to :math:`\frac{f_s}{2}` represent different sky-frequencies when the input analog signals are mixed with LOs upstream of the digital system.

As shown in :numref:`fig-ata-rfsoc-feng`, the PFB receives real-valued broad-band data with 16-bits resolution (though only the most-significant 14 bits are populated by the ADC), and after processing delivers complex-valued spectra with 25-bit resolution.

Internally, the FFT data path is shown in :numref:`fig-pfb-bitwidth-rfsoc`.

.. figure:: _static/figs/pfb-bitwidth-rfsoc.png
    :align: center
    :name: fig-pfb-bitwidth-rfsoc
    
    A pictorial representation of the PFB internal datapath, showing internal data precision. Coefficients in the FIR and FFT modules are stored with 18 bits resolution. Overall signal amplitude growth in the FFT is controlled with a *shift schedule*, which is hardcoded to enforce :math:`2^{-12}` scaling. This is sufficient to guarantee against FFT overflow for any input signal.

In general, an FFT with :math:`2^N` points has :math:`N` butterfly stages, and dynamic range should grow by :math:`N` bits to guarantee against overflow.

Relevant Software Methods
`````````````````````````

  - ``fft_of_detect``: Count overflows in the FFT module
  - ``spec_read``: Read an accumulated spectrum
  - ``spec_plot``: Plot an accumulated spectrum

Spectral Power Accumulator
~~~~~~~~~~~~~~~~~~~~~~~~~~

The Spectral Power Accumulator generates auto-correlation power-spectra for the two input data streams.

Spectra are computed by:

  #. Multiplying 25-bit voltage inputs to generate 50-bit powers
  #. Integrating these powers into 64-bit accumulators, with a runtime-configurable integration length

The nature of the bit handling in this implementation means that the accumulators can only guarantee against overflow for integrations of fewer than :math:`2^{14}` spectra. This amounts to just 53 ms of data.
In practice, except in cases of high-power narrowband inputs, integrations of substantially longer without overflow are possible.
In the event of overflow, data are saturated at :math:`\pm 2^{63}`.

Spectra can be read from the power accumulator via software -- appropriate for monitoring, debugging, and low time-resolution (~1s) observations.

A test vector injection module exists for the purposes of testing the spectrometer pipeline.
When activated, this module replaces PFB data with a test pattern whose real parts are zero, and whose imaginary parts form a counter.
For the X-polariaztion, FFT channel :math:`i` takes the value :math:`32*(8 floor(\frac{i}{4}) + mod(i, 4))`.
For the Y-polariaztion, FFT channel :math:`i` takes the value :math:`32*(8 floor(\frac{i}{4}) + mod(i, 4)) + 4`.

Scaling in the spectrometer is such that the test vector inputs appear at the accumulator input with FFT channel :math:`i` having the values:

  - For the X-polarization: :math:`8*floor(\frac{i}{4}) + mod(i, 4)`.
  - For the Y-polarization: :math:`8*floor(\frac{i}{4}) + mod(i, 4) + 4`.

This pattern can be checked against observed output data to verify that the two polarizations are being correctly identified, and accumulation length is being correctly set.

Relevant Software Methods
`````````````````````````
  - ``set_accumulation_length``: Set the number of spectra to be accumulated
  - ``spec_read``: Read an accumulated spectrum
  - ``spec_plot``: Plot an accumulated spectrum
  - ``spec_test_vector_mode``: Turn on and off the spectrometer test-vector mode

Equalization
~~~~~~~~~~~~

In the voltage pipeline, post-PFB data are quantized to 8 bits prior to being transmitted over 100 GbE.

This substantial reduction of bit precision requires carefully managing input signal levels.
As such, prior to equalization, spectra are multiplied by a runtime-programmable amplitude scaling factor.
The scaling factors can be uniquely specified per polarization and per frequency channel, and should be used to ensure that data in each frequency channel exhibit an appropriate RMS.

Equalization coefficients can be computed by inferring power levels from the inbuilt spectral-power accumulator.

Relevant Software Methods
`````````````````````````

  - ``eq_load_coeffs``: Load a set of equalization coefficients

Voltage Channel Selection
~~~~~~~~~~~~~~~~~~~~~~~~~

The Voltage Mode output data path requires that only 2048 of the 4096 generated frequency channels are transmitted over 10 GbE.
This down-selection takes place following 4-bit quantization, and is typically configured at initialization time using an appropriate configuration file (see `sec-config-file`).

The chosen 2048 channels are split into eight groups of 256 channels, each of which may be directed to a different IP address.

Channel selection should satisfy the following rules:

  1. Each destination IP address should receive a start channel which is an integer multiple of 32.
  2. If channel :math:`n` is sent to IP address :math:`I`, this IP address should also receive channels :math:`n+1,n+2,n+3,n+4,n+5,n+6,n+7`.

Beyond these requirements, channels selected for transmission need not be contiguous and may also be duplicated. I.e. a block of 512 channels may be sent to each of 4 IP addresses.

Relevant Software Methods
`````````````````````````

  - ``select_output_channels``: Select which frequency channels are to be sent over 10 GbE
  - ``eq_load_test_vectors``: Load a custom set of test vectors into the voltage data path
  - ``eq_test_vector_mode``: Turn on or off voltage test vector injection

100Gb Ethernet
~~~~~~~~~~~~~~~~~~~~~~~~~~

Relevant Software Methods
`````````````````````````

  - ``eth_reset``: Reset the Ethernet core
  - ``eth_set_mode``: Choose between spectrometer and voltage 10GbE outputs
  - ``eth_set_dest_port``: Set the destination UDP port for 10GbE traffic
  - ``eth_enable_output``: Turn on 100GbE transmission
  - ``eth_print_counters``: Print Ethernet packet statistics


Relevant Software Methods
`````````````````````````
.. _sec-runtime-control:

Run-time Control
----------------

Installing the Control Library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *ata_snap* python library is provided to control the F-Engine firmware design. It requires Python >=3.5 and the following custom python libraries:

#. casperfpga (a control library for interacting with CASPER hardware, such as SNAP boards)
#. adc5g (a library for configuring the ADC5G card)

These libraries are bundled in the *ata_snap* repository to minimize issues with library version compatibility.

To install the control libraries:

.. code-block:: console

  # Clone the ata_snap repository
  git clone https://github.com/realtimeradio/ata_snap

  # Clone relevant sub-repositories
  cd ata_snap
  git submodule init
  git submodule update

  # Install casperfpga
  cd sw/casperfpga
  # Install casperfpga dependencies (requires pip, which can be installed with `apt install python3-pip`
  pip install -r requirements.txt
  # Install casperfpga
  python setup.py install

  # Install the adc5g library
  cd ../adc5g/adc5g
  python setup.py install

  # Install the ata_snap library
  cd ../../../ata_snap
  python setup.py install

If the library has installed correctly, in a Python shell, you should be able to successfully execute

.. code-block:: python

  from ata_snap import ata_snap_fengine

Configuration Recipes
---------------------

Simple use of the *ata_snap* library comprises the following steps:

#. Program the RFSoC boards with appropriate firmware
#. Configure any runtime settings
#. Synchronize RFSoC boards with UTC
#. Turn on data flow

Once these steps are complete, data will be transmitted over Ethernet and downstream software can catch and process this data as desired.

For a single SNAP board, all of these steps can be carried out at once using a provided intialization scrips ``snap_feng_init.py``.
This script has the following use template:

.. code-block:: console

  $ snap_rfsoc_init.py -h
  usage: snap_feng_init.py [-h] [-s] [-t] [--eth_spec] [--eth_volt] [-a ACCLEN]
                           [-f FFTSHIFT] [--specdest SPECDEST]
                           host fpgfile configfile
  
  Program and initialize a SNAP ADC5G spectrometer
  
  positional arguments:
    host                 Hostname / IP of SNAP
    fpgfile              .fpgfile to program
    configfile           Configuration file
  
  optional arguments:
    -h, --help           show this help message and exit
    -s                   Use this flag to re-arm the design's sync logic
                         (default: False)
    -t                   Use this flag to switch to post-fft test vector outputs
                         (default: False)
    --eth_spec           Use this flag to switch on Ethernet transmission of the
                         spectrometer (default: False)
    --eth_volt           Use this flag to switch on Ethernet transmission of
                         F-engine data (default: False)
    -a ACCLEN            Number of spectra to accumulate per spectrometer dump.
                         Default: get from config file (default: None)
    --specdest SPECDEST  Destination IP address to which spectra should be sent.
                         Default: get from config file (default: None)


.. _sec-config-file:

Configuration File
~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

  # Accumulation length, in spectra.
  acclen: 300000
  # Coeffs should be a single number, or an array
  # of 4096 numbers to set one coefficient per channel.
  coeffs: 100
  # UDP port for 10GbE data
  dest_port: 10000
  spectrometer_dest: 10.11.10.173
  # Define which channels should be output
  # over 10GbE in voltage dump mode.
  voltage_output:
    start_chan: 0
    n_chans: 1024
    # Channels will be spread over the following
    # destinations so that the first n_chans // len(dests)
    # go to the first IP address, etc.
    dests:
        - 10.11.10.173
  # All relevant IP/MAC mapping should be manually
  # specified here
  arp:
    10.11.10.173: 0xaeecc7b400ff
    10.11.10.174: 0xaeecc7b400a0

