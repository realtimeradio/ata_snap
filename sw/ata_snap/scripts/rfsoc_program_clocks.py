import argparse
import time

import casperfpga
import casperfpga.i2c as i2c
import casperfpga.i2c_mux as i2c_mux
import casperfpga.i2c_spi as i2c_spi
import casperfpga.i2c_sfp as i2c_sfp
import casperfpga.synth as synth
import sys


parser = argparse.ArgumentParser(description='Program RFSoC Clocks over I2C',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('host', type=str,
                    help = 'Hostname / IP of RFSoC')
parser.add_argument('--lmkconf', dest='lmkconf', default=None,
                    help ='File containing LMK configuration')
parser.add_argument('--lmxconf', dest='lmxconf', default=None,
                    help ='File containing LMX configuration')
parser.add_argument('--siconf', dest='siconf', default=None,
                    help ='File containing Si5241 configuration')
parser.add_argument('--sfpstat', dest='sfpstat', action="store_true",
                    help ='Read SFP status information')
args = parser.parse_args()

r = casperfpga.CasperFpga(args.host, transport=casperfpga.KatcpTransport)
i2c_dev = i2c.I2C(r, 'i2c_interface')

i2c_mux_dev = i2c_mux.PCA9548A(i2c_dev, 1)

# Read LMK configuration
if args.lmkconf is not None:
    print("Using %s" % args.lmkconf)
    lmk_addr_data = []
    with open(args.lmkconf, "r") as fh:
        for line in fh.readlines():
            lmk_addr_data += [int(line.split("\t")[1], 16)]

    i2c_mux_dev.set_output(1<<0)
    i2c_spi_dev_lmk = i2c_spi.SC18IS602(i2c_dev, addr=0b110)
    i2c_spi_dev_lmk.set_spi_config(0x03)
    lmk = synth.LMXRaw(i2c_spi_dev_lmk, cs=1<<0)

    # Write the LMK chip registers
    for x in lmk_addr_data:
        readback = lmk.send(x)

# Now do the LMX chips
if args.lmxconf is not None:
    print("Using %s" % args.lmxconf)
    lmx_addr_data = []
    with open(args.lmxconf, "r") as fh:
        for line in fh.readlines():
            lmx_addr_data += [int(line.split("\t")[1], 16)]

    i2c_mux_dev.set_output(1<<4)
    i2c_spi_dev_lmx = i2c_spi.SC18IS602(i2c_dev, addr=0b010)
    i2c_spi_dev_lmx.set_spi_config(0x03)
    
    lmxs = [
            synth.LMXRaw(i2c_spi_dev_lmx, cs=1<<0),
            synth.LMXRaw(i2c_spi_dev_lmx, cs=1<<1),
          ]
    
    # Write the LMX chip registers
    for lmx in lmxs:
        for x in lmx_addr_data:
            readback = lmx.send(x)

# And finally SI chip

if args.siconf is not None:
    print("Using %s" % args.siconf)
    si_addr_data = []
    with open(args.siconf, "r") as fh:
        for line in fh.readlines():
            # Ignore comments
            if line.startswith("#"):
                continue
            # Ignore column header
            if line.startswith("Address"):
                continue
            addr, data = line.split(",")
            si_addr_data += [[int(addr, 16), int(data, 16)]]

    i2c_mux_dev.set_output(1<<6)

    print(si_addr_data)
    # Write the chip registers
    chip_addr = 0b1110100
    current_page = 0x0
    i2c_dev.write(chip_addr, 0x1, current_page)
    for addr, data in si_addr_data:
        page = (addr>>8) & 0xff
        if page != current_page:
            print("Setting page to %d" % page)
            i2c_dev.write(chip_addr, 0x1, page)
            current_page = page
        payload = [addr&0xff, data]
        i2c_dev.write(chip_addr, payload)
        if addr == 0x0B4E:
            print("Waiting 300ms after config preamble")
            time.sleep(0.3)

if args.sfpstat:
    sfp = i2c_sfp.Sfp(i2c_dev, target_clock_khz=50.)
    for mux_sel in [1,5]:
        i2c_mux_dev.set_output(1<<mux_sel)
        try:
            stat = sfp.get_status()
            print('%s status (mux %d):' % (sfp.itf.controller_name, mux_sel))
            for k, v in stat.items():
                print('    %s: %s' % (k, v))
        except OSError:
            print('Error getting status from %s (mux %d)' % (sfp.itf.controller_name, mux_sel))

