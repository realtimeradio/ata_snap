# `snap_adc5g_feng` Control Software

The control software for the `snap_adc5g_feng` firmware consists of a simple Python class providing an API to
the most commonly required functionality.

An initialization script `snap_feng_init.py` and basic configuration file `config/ataconfig.yml` provide a simple
mechanism to configure a board, and serve as an example to some of the API elements.

## Software Versions

Provided software supports Python 3 only. Key dependencies are provided as submodules in this repository. Use of a python virtual environment is strongly recommended. Use `git submodule update` to ensure you are building against the correct version of the bundled dependency libraries.

### `adc5g`

The ADC5g library provides control of the external ADC card. Install with:
```
cd adc5g/adc5g
python setup.py install
```

### `casperfpga`
The `casperfpga` library provides a control interface for a variety of CASPER FPGA boards. Install with:
```
cd casperfpga
pip install -r requirements.txt
python setup.py install
```

### `ata_snap`
The control library itself can be installed with:
```
cd ata_snap
python setup.py install
```

### Further dependencies
This software also requires:
- `pyaml`

These can be installed via `pip` or your python package manager of choice.

## Initializing a SNAP board

The `snap_feng_init.py` script will initialize an unprogrammed SNAP board. Usage:

```
(my-python3-virtual-env) user@host:$ snap_feng_init.py -h
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
  -f FFTSHIFT          FFT shift schedule. Default: get from configuration
                       file (default: None)
  --specdest SPECDEST  Destination IP address to which spectra should be sent.
                       Default: get from config file (default: None)
```

`fpgfile` should be a compiled bitstream generated from the `snap_adc5g_feng.slx` model by the CASPER toolflow.
`host` is the SNAP board you wish to program
`configfile` is the path to a configuration file specifying system configuration parameters including:
- channel output configurations
- IP addresses of systems on the network
- defaults for options which can also be set with command line flags.

## Interacting with a SNAP board after initialization

After initialization, you may interface with the running SNAP board using the ata_snap library. For example:

```python
# Create an F-Engine instance
from ata_snap import ata_snap_fengine
feng = ata_snap_fengine.AtaSnapFengine(<SNAP hostname or IP>)

# Gather information about the currently running firmware design
feng.fpga.get_system_information(<path/to/programmed/fpg/file>)

# Change configuration...
# Set equalization coefficients to 100
# First polarization:
feng.eq_load_coeffs(0, 100)
# Second polarization:
feng.eq_load_coeffs(1, 100)

# Print 10GbE packet output stats
feng.eth_print_counters()

# Grab some ADC samples
x_samples, y_samples = feng.adc_get_samples()

# calculate mean / variance
import numpy
x_mean = np.mean(x_samples)
x_var = np.var(x_samples)

# etc...
```
