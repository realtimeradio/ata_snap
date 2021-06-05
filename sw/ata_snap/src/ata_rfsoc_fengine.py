import casperfpga
import struct
import logging
import numpy as np
import time
from . import ata_snap_fengine
from .ata_snap_fengine import _ip_to_int, _int_to_ip

TGE_N_SAMPLES_PER_WORD = 8 # 8 1-byte time samples per 512-bit 10GbE input. TODO: what about 8-bit mode?

class AtaRfsocFengine(ata_snap_fengine.AtaSnapFengine):
    """
    This is a class which implements methods for programming
    and communicating with an RFSoC board running the ATA F-Engine
    firmware.

    :param host: Hostname of board associated with this instance.
    :type host: str
    :param feng_id: Antenna ID of the antenna connected to this SNAP.
        This value is used in the output headers of data packets.
    :type feng_id: int

    :param pipeline_id: pipeline ID of the antenna connected to this SNAP.
        This value is used to associate an F-Engine with a pipeline instance
    :type pipeline_id: int
    """
    pps_source = "board" #: After programming set the PPS source to the front panel input
    n_interfaces = 1     #: Number of available 10GbE interfaces
    n_ants_per_board = 8 #: Number of antennas on a board
    n_chans_per_block = 32 #: Number of channels reordered in a single word
    packetizer_granularity = 2**8 # Number of 64-bit words ber packetizer step
    def __init__(self, host, feng_id=0, pipeline_id=0):
        """
        Constructor method
        """
        self.fpga = casperfpga.CasperFpga(host, transport=casperfpga.KatcpTransport)
        self.fpga.is_little_endian = True # seems to have issues autodetecting?
        self.host = host
        self.logger = logging.getLogger('AtaRfsocFengine')
        self.logger.setLevel(logging.DEBUG)
        self.feng_id = feng_id
        self.pipeline_id = pipeline_id
        # If the board is programmed, try to get the fpg data
        #if self.is_programmed():
        #    try:
        #        self.fpga.transport.get_meta()
        #    except:
        #        self.logging.warning("Tried to get fpg meta-data from a running board and failed!")

    def _pipeline_get_regname(self, regname):
        """
        Modify register name ``regname`` to comply with pipeline naming
        conventions.

        :param regname: The register name in this pipeline to be accessed.
        :type regname: str

        :return: Expanded register name, matching the spec recognized
            by CasperFpga.
        :rtype: str
        """
        return "pipeline%d_" % self.pipeline_id + regname

    def program(self, fpgfile):
        """
        Program a SNAP with a new firmware file.

        :param fpgfile: .fpg file containing firmware to be programmed
        :type fpgfile: str
        """
        # in an abuse of the casperfpga API, only the TapcpTransport has a "force" option
        if isinstance(self.fpga.transport, casperfpga.TapcpTransport):
            self.fpga.transport.upload_to_ram_and_program(fpgfile, force=force)
        else:
            self.fpga.upload_to_ram_and_program(fpgfile)
        self.fpga.get_system_information(fpgfile)
        self.sync_select_input(self.pps_source)
        self.spec_set_pipeline_id()

    def spec_set_pipeline_id(self):
        self.fpga.write_int(self._pipeline_get_regname("corr_feng_id"), self.feng_id)

    def spec_read(self, mode="auto", flush=False, normalize=False):
        """
        Read a single accumulated spectrum.

        This method requires that the currently programmed fpg file is known.
        This can be achieved either by programming the board with program(<fpgfile>),
        or by running fpga.get_system_information(<fpgfile>) if the board
        was already programmed outside of this class.

        :param mode: "auto" to read an autocorrelation for each of the X and Y pols.
            "cross" to read a cross-correlation of Xconj(Y).
        :type mode: str:
        :param flush: If True, throw away one integration prior to getting data.
                      This can be desirable if (eg) EQ coefficients have been recently
                      changed.
        :type flush: Bool
        :param normalize: If True, divide out the accumulation length and firmware
            scaling, returning floating point values. Otherwise, return integers
            and leave these factors present.
        :type normalize: Bool

        :raises AssertionError: if mode is not "auto" or "cross"
        :return: If mode="auto": A tuple of two numpy arrays, xx, yy, containing
            a power spectrum from the X and Y polarizations.
            If mode="cross": A complex numpy array containing the cross-power
            spectrum of Xconj(Y).
        :rtype: numpy.array
        """
        SCALE = 2**48 # Vacc number representation
        if len(self.fpga.snapshots) == 0:
            raise RuntimeError("Please run AtaSnapFengine.program(...) or "
                    "AtaSnapFengine.fpga.get_system_information(...) with the "
                    "loaded bitstream prior to trying to snapshot data")

        assert mode in ["auto", "cross"]
        if mode == "auto":
            v = 0
        else:
            v = 1
        devs = self.fpga.listdev()
        for i in range(self.n_ants_per_board):
            regname = 'pipeline%d_corr_enable_ss_output' % i
            if regname not in devs:
                continue
            if i == self.pipeline_id:
                self.fpga.write_int(regname, 1)
            else:
                self.fpga.write_int(regname, 0)
        self.fpga.write_int("vacc_ss_sel", v)
        ss0 = self.fpga.snapshots['vacc_ss_ss0']
        ss1 = self.fpga.snapshots['vacc_ss_ss1']
        ss2 = self.fpga.snapshots['vacc_ss_ss2']
        ss3 = self.fpga.snapshots['vacc_ss_ss3']

        # Get the accumulation length if we need it for scaling
        if normalize:
            acc_len = self.get_accumulation_length()

        if flush:
            ss0.read_raw()

        ss0.arm() # This arms all RAMs
        d0, t0 = ss0.read_raw(arm=False)
        d1, t1 = ss1.read_raw(arm=False)
        d2, t2 = ss2.read_raw(arm=False)
        d3, t3 = ss3.read_raw(arm=False)
        d0i = struct.unpack(">%dq" % (d0["length"] // 8), d0["data"])
        d1i = struct.unpack(">%dq" % (d1["length"] // 8), d1["data"])
        d2i = struct.unpack(">%dq" % (d2["length"] // 8), d2["data"])
        d3i = struct.unpack(">%dq" % (d3["length"] // 8), d3["data"])
        if mode == "auto":
            xx_0  = d0i[0::2]
            xx_1  = d1i[0::2]
            xx_2  = d2i[0::2]
            xx_3  = d3i[0::2]
            yy_0  = d0i[1::2]
            yy_1  = d1i[1::2]
            yy_2  = d2i[1::2]
            yy_3  = d3i[1::2]
            xx = np.zeros(self.n_chans_f, dtype=np.int64)
            yy = np.zeros(self.n_chans_f, dtype=np.int64)
            for i in range(self.n_chans_f // 4):
                xx[4*i]   = xx_0[i]
                xx[4*i+1] = xx_1[i]
                xx[4*i+2] = xx_2[i]
                xx[4*i+3] = xx_3[i]
                yy[4*i]   = yy_0[i]
                yy[4*i+1] = yy_1[i]
                yy[4*i+2] = yy_2[i]
                yy[4*i+3] = yy_3[i]
            if normalize:
                xx = xx / float(SCALE * acc_len)
                yy = yy / float(SCALE * acc_len)
            return xx, yy
        elif mode == "cross":
            xy_0_r = d0i[0::2]
            xy_0_i = d0i[1::2]
            xy_1_r = d1i[0::2]
            xy_1_i = d1i[1::2]
            xy_2_r = d2i[0::2]
            xy_2_i = d2i[1::2]
            xy_3_r = d3i[0::2]
            xy_3_i = d3i[1::2]
            xy = np.zeros(self.n_chans_f, dtype=np.complex)
            for i in range(self.n_chans_f // 4):
                xy[4*i]   = xy_0_r[i] + 1j*xy_0_i[i]
                xy[4*i+1] = xy_1_r[i] + 1j*xy_1_i[i]
                xy[4*i+2] = xy_2_r[i] + 1j*xy_2_i[i]
                xy[4*i+3] = xy_3_r[i] + 1j*xy_3_i[i]
            if normalize:
                xy = xy / float(SCALE * acc_len)
            return xy

    def adc_get_samples(self):
        """
        Get a block of samples from both ADC inputs, captured simultaneously.

        This method requires that the currently programmed fpg file is known.
        This can be achieved either by programming the board with program(<fpgfile>),
        or by running fpga.get_system_information(<fpgfile>) if the board
        was already programmed outside of this class.

        :return: x, y (numpy arrays of ADC sample values)
        :rtype: numpy.ndarray
        """
        if len(self.fpga.snapshots) == 0:
            raise RuntimeError("Please run AtaRfsocFengine.program(...) or "
                    "AtaRfsocFengine.fpga.get_system_information(...) with the "
                    "loaded bitstream prior to trying to snapshot data")
        self.fpga.write_int('sel0', 2*self.pipeline_id)
        self.fpga.write_int('sel1', 2*self.pipeline_id + 1)
        dx, t = self.fpga.snapshots.ss_adc0.read_raw(man_trig=True, man_valid=True)
        dy, t = self.fpga.snapshots.ss_adc1.read_raw(man_trig=True, man_valid=True)
        x = struct.unpack(">%dh" % (dx['length']//2), dx['data'])
        y = struct.unpack(">%dh" % (dy['length']//2), dy['data'])
        return x, y

    def eq_load_test_vectors(self, pol, tv):
        """
        Load test vectors for the Voltage pipeline test vector injection module.

        :param pol: Selects which polarization vectors are being loaded to (0 or 1)
            0 is the first ADC input, 1 is the second.
        :type pol: int
        :param tv: Test vectors to be loaded. `tv` should have self.n_chans_f
            elements. tv[i] is the test value for channel i.
            Each value should be an 8-bit number - the most-significant
            4 bits are interpretted as the 4-bit, signed, real part of
            the data stream. The least-significant 4 bits are interpretted
            as the 4-bit, signed, imaginary part of the data stream.
        :type tv: numpy.ndarray or list of ints
        :raises AssertionError: If an array of test vectors is provided with an invalid size,
            or if pol is a non-allowed value
        """
        tv = list(tv)
        assert len(tv) == self.n_chans_f
        assert pol in [0, 1]
        tv_8bit = [x%256 for x in tv]
        tv_8bit_str = struct.pack('>%dB'%self.n_chans_f, *tv_8bit)
        regname = self._pipeline_get_regname('eqtvg_pol%d_tv' % pol)
        # Strange issue where large writes don't work on RFSoC?
        for i in range(len(tv_8bit_str) // 4):
            self.fpga.write(regname,
                            tv_8bit_str[4*i:4*(i+1)],
                            offset=4*i,)
        # verify
        readback = self.fpga.read(regname, len(tv_8bit_str))
        assert tv_8bit_str == readback, "Readback failed!"

    def select_output_channels(self, start_chan, n_chans, dests=['0.0.0.0'], n_interfaces=None, n_bits=4):
        """
        Select the range of channels which the voltage pipeline should output.

        Example usage:
            Send channels 0..255 to 10.0.0.1:
                select_output_channels(0, 256, dests=['10.0.0.1'])
            Send channels 0..255 to 10.0.0.1, and 256..512 to 10.0.0.2
                select_output_channels(0, 512, dests=['10.0.0.1', '10.0.0.2'])

        :param start_chan: First channel to output
        :type start_chan: int
        :param n_chans: Number of channels to output
        :type n_chans: int
        :param dests: List of IP address strings to which data should be sent.
            The first n_chans / len(dests) will be sent to dest[0], etc..
        :type dests: list of str
        :param n_interfaces: Number of 10GbE interfaces to use. Should be <= self.n_interfaces
            Default to using all available interfaces.
        :type n_interface: int

        :raises AssertionError: If the following conditions aren't met:
            `start_chan` should be a multiple of self.n_chans_per_block (4)
            `n_chans` should be a multiple of self.n_chans_per_block (4)
            `interface` should be <= self.n_interfaces

        :return: A dictionary, keyed by destination IP, with values corresponding to the
            ranges of channels destined for this IP.
            Eg, if sending 512 channels over two destinations
            '10.0.0.10' and '10.0.0.11', this function might return
            {'10.0.0.10': [0,1,..,255], '10.0.0.11': [256,257,..,511]}
        :rtype: dict
        """

        # Each 10GbE core in the design has its own packetizer.
        # Each packetizer has internal state which changes every packetizer_granularity
        # FPGA clock ticks (each clock tick = one 64-bit word).
        # For each packetizer step, a block of packetizer_granularity words can
        # be marker either
        #    1. The first block in a packet
        #    2. A block in the middle of a packet
        #    3. The last block in a packet
        #    4. Not part of a valid block
        # Accordingly, the block will be marked as valid (or not) and a 
        # 2-word header, will be inserted before the block of data, or an
        # EOF pulse will be inserted at the end of the block.

        # It is the job of the upstream reordering to ensure that the block immediately
        # preceding the first block of a packet contains data which is not to be sent.
        # This creates the space for header insertion.
        # Upstream reordering should also intersperse channels to be sent with those
        # to be discarded, in order to limit the output data rate to <10Gb/s

        # In the event that 4-bit mode is used, the same data is sent to multiple
        # packetizers, and this function should ensure half the channels are sent from
        # each port.
        # In the event that 8-bit mode is used, 1/n_interfaces of the total generated
        # channels are sent to each packetizer, and marking of packet boundaries should
        # be dealt with accordingly.

        # Currently, the only mode allowed outputs data in [slowest to fastest]
        # chan x time x polarization x complexity ordering, though the firmware
        # also has the capability to generate data in
        # chan x time x chans-per-packet x pol x complexity ordering.
        

        # Data by first reordering n_chans_f * n_times_per_packet
        # spectra using a programmable reorder. This reorder operates on
        # n_chans_f * n_times_per_packet / nchans_per_block words, with each word
        # 8+8 bits x nchans_per_block x 2 [pols] wide.

        feng_id = self.feng_id

        # default to using all the interfaces
        n_interfaces = n_interfaces or self.n_interfaces
        assert n_interfaces <= self.n_interfaces

        # define maximum number of channels per packet such that max packet
        # size is 8 kByte + header
        assert n_bits in [4], "Only 4-bit output modes is supported!"
        max_chans_per_packet = 8*8192 // (2*n_bits) // self.n_times_per_packet // 2

        # Figure out the channel granularity of the packetizer. This operates
        # in blocks of packetizer_granularity 64-bit words.
        # For now, we only consider case with time the faster axis.
        times_per_word = 8*TGE_N_SAMPLES_PER_WORD // (2*2*n_bits)
        # This should always be True for reasonable firmware
        assert self.packetizer_granularity % times_per_word == 0
        packetizer_chan_granularity = self.packetizer_granularity // times_per_word

        # We reorder n_chans_per_block as parallel words, so must deal with
        # start / stop points with that granularity
        assert start_chan % self.n_chans_per_block == 0
        n_dests = len(dests)
        # Also Demand that the number of channels can be equally divided
        # among the destination addresses
        assert n_chans % (n_dests * self.n_chans_per_block) == 0
        # Number of channels per destination is now gauranteed to be an integer
        # multiple of n_chans_per_block
        n_chans_per_destination = n_chans // n_dests
        # If the channels per destination is > the max, then split into multiple
        # packets
        n_packets_per_destination = int(np.ceil(n_chans_per_destination / max_chans_per_packet))
        # Channels should be able to be divided up into packets equally
        assert n_chans_per_destination % n_packets_per_destination == 0
        n_chans_per_packet = n_chans_per_destination  // n_packets_per_destination
        # Number of channels per packet should be a multiple of the reorder granularity
        assert n_chans_per_packet % self.n_chans_per_block == 0
        # Number of channels per packet should be a multiple of packetizer granularity
        assert n_chans_per_packet % packetizer_chan_granularity == 0
        n_slots_per_packet = n_chans_per_packet // packetizer_chan_granularity
        # Can't send more than all the channels!
        assert start_chan + n_chans <= self.n_chans_f

        self.logger.info('Start channel: %d' % start_chan)
        self.logger.info('Number of channels to send: %d' % n_chans)
        self.logger.info('Number of interfaces to be used: %d' % n_interfaces)
        self.logger.info('Number of interfaces available: %d' % self.n_interfaces)

        self.logger.info('Number of destinations: %d' % n_dests)
        self.logger.info('Number of channels per destination: %d' % n_chans_per_destination)
        self.logger.info('Number of channels per packet: %d' % n_chans_per_packet)

        # First, for simplicity, duplicate the destination list so that
        # we can deal exclusively in packets, with nominally 1 packet per destination,
        # even if some destinations appear more than once.
        dup_dests = []
        for dest in dests:
            for i in range(n_packets_per_destination):
                dup_dests += [dest]
        dests = dup_dests

        # Divide up each packetizer input stream of n_times_per_pkt * n_chans_f
        # into blocks of packetizer_chan_granularity
        packetizer_n_blocks = self.n_chans_f // packetizer_chan_granularity
        print("packetizer n blocks:", packetizer_n_blocks)
        print("packetizer granularity:", packetizer_chan_granularity)
        # Initialize variable for the headers
        headers = [
                      [
                          {
                               'first': False,
                               'valid': False,
                               'last': False,
                               'dest': '0.0.0.0',
                               'chans': [0] * packetizer_chan_granularity,
                               'feng_id' : self.feng_id,
                               'n_chans' : n_chans_per_packet,
                               'is_8_bit' : n_bits == 8,
                               'is_time_fastest' : True,
                          } for i in range(packetizer_n_blocks)
                      ]
                  for j in range(n_interfaces)]

        chan_reorder_map = -1 * np.ones(self.n_chans_f, dtype=np.int32)

        # How many slots packetizer blocks do we need to use?
        # Lazily force data rate out of each interface to be the same
        n_packets = len(dup_dests)
        assert n_packets % n_interfaces == 0, "Number of destination packets (%d) does not divide evenly betweed %d interfaces" % n(n_packets, _interfaces)
        available_blocks = packetizer_n_blocks * n_interfaces
        needed_blocks = n_chans // packetizer_chan_granularity
        spare_blocks = available_blocks - needed_blocks

        self.logger.info('Available blocks: %s' % available_blocks)
        self.logger.info('Required blocks: %s' % needed_blocks)
        self.logger.info('Spare blocks: %s' % spare_blocks)

        spare_blocks_per_packet = int(np.floor(spare_blocks / n_packets))
        self.logger.info('Spare blocks per packet: %s' % spare_blocks_per_packet)

        # So, however many packetizer blocks sending a packet takes, after the last
        # block in packet, the next `spare_blocks_per_packet` can be marked invalid

        # Now start allocating channels to slots
        interface = 0
        slot = [0 for _ in range(n_interfaces)]
        input_chan_id = 0
        slot_start_chan = start_chan
        for p in range(n_packets):
            for s in range(n_slots_per_packet):
                headers[interface][slot[interface]]['first'] = s==0
                headers[interface][slot[interface]]['valid'] = True
                headers[interface][slot[interface]]['last'] = s==(n_slots_per_packet-1)
                headers[interface][slot[interface]]['dest'] = dup_dests[p]
                headers[interface][slot[interface]]['chans'] = range(slot_start_chan, slot_start_chan + packetizer_chan_granularity)
                input_chan_id = slot[interface] * packetizer_chan_granularity
                #print(p, s, input_chan_id)
                chan_reorder_map[input_chan_id : input_chan_id + packetizer_chan_granularity] = range(slot_start_chan, slot_start_chan + packetizer_chan_granularity)
                slot_start_chan += packetizer_chan_granularity
                slot[interface] += 1
            # If we are in 4-bit mode, the data going in to both interfaces is the same,
            # so the next interface should start at the slot after the interface we have just used
            if n_bits == 4:
                slot[(interface + 1) % n_interfaces] = slot[interface]
            # After a packet we have dead time
            slot[interface] += spare_blocks_per_packet
            interface = (interface + 1) % n_interfaces
            
        #for i in range(n_interfaces):
        #    for j in range(packetizer_n_blocks):
        #        print(i,j,headers[i][j])
        # Load the headers
        for i in range(n_interfaces):
            self._populate_headers(i, headers[i], offset=self.pipeline_id*available_blocks)
        
        # Load the chan reorder map

        # reduce the channel reorder map by the number of parallel chans in a reorder word
        chan_reorder_map = chan_reorder_map[::self.n_chans_per_block]
        for cn, c in enumerate(chan_reorder_map):
            if c == -1:
                continue
            assert (c % self.n_chans_per_block) == 0
            chan_reorder_map[cn] /= self.n_chans_per_block
        # fill in the gaps (indicated by -1) in the above map with allowed channels we haven't used
        # Note that you _cannot_ repeat channels in the map, since we aren't double buffering
        possible_chans = list(range(0, self.n_chans_f // self.n_chans_per_block))
        for c in chan_reorder_map:
            if c == -1:
                continue
            possible_chans.remove(c)
        for i in range(len(chan_reorder_map)):
            if chan_reorder_map[i] == -1:
                chan_reorder_map[i] = possible_chans.pop(0)
        self._reorder_channels(chan_reorder_map)

        # Return a dictionary, keyed by destination address, where each entry is the range of channels being
        # send to that address.
        rv = {}
        for dn, d in enumerate(dests):
            rv[d] = list(range(start_chan + dn*n_chans_per_destination,
                          start_chan + (dn+1)*n_chans_per_destination))
        return rv

    def _populate_headers(self, interface, headers, offset=0):
        """
        Populate the voltage mode packetizer header fields.

        :param interface: The 10GbE interface to populate
        :type interface: int
        :param headers: A list of header dictionaries to populate
        :type headers: list

        Entry `i` of the `headers` list is written to packetizer header BRAM index `i`.
        This represents the control word associated with the `i`th data sample block
        after a sync pulse. Each data block is self.packetizer_granularity words.

        Each `headers` entry should be a dictionary with the following fields:
          - `first`: Boolean, indicating this sample block is the first in a packet.
          - `valid`: Boolean, indicating this sample block contains valid data.
          - `last`: Boolean, indicating this is the last valid sample block in a packet.
          - `is_8_bit`: Boolean, indicating this packet contains 8-bit data.
          - `is_time_fastest`: Boolean, indicating this packet has a payload in
            channel [slowest] x time x polarization [fastest] order.
          - `n_chans`: Integer, indicating the number of channels in this data block's packet.
          - `chans`: list of ints, indicating the channels present in this data block. The zeroth element is the first channel in this block.
          - `feng_id`: Integer, indicating the F-Engine ID of this block's data.
            This is usually always `self.feng_id`, but may vary if one board is spoofing
            traffic from multiple boards.
          - `dest` : String, the destination IP of this data block (eg "10.10.10.100")
        """

        h_bytestr = b''
        ip_bytestr = b''
        for h in headers:
            header_word = (int(h['last']) << 58) \
                        + (int(h['valid']) << 57) \
                        + (int(h['first']) << 56) \
                        + (int(h['is_8_bit']) << 49) \
                        + (int(h['is_time_fastest']) << 48) \
                        + ((h['n_chans'] & 0xffff) << 32) \
                        + ((h['chans'][0] & 0xffff) << 16) \
                        + ((h['feng_id'] & 0xffff) << 0)
            h_bytestr += struct.pack('>Q', header_word)
            ip_bytestr += struct.pack('>I', _ip_to_int(h['dest']))
        for i in range(len(ip_bytestr) // 4):
            self.fpga.write(self._pipeline_get_regname('packetizer%d_ips' % interface), ip_bytestr[4*i:4*(i+1)], offset=4*i+8*offset)
        assert self.fpga.read(self._pipeline_get_regname('packetizer%d_ips' % interface), len(ip_bytestr), offset=8*offset) == ip_bytestr, "Readback failed!"
        for i in range(len(h_bytestr) // 4):
            self.fpga.write(self._pipeline_get_regname('packetizer%d_header' % interface), h_bytestr[4*i:4*(i+1)], offset=4*i+8*offset)
        assert self.fpga.read(self._pipeline_get_regname('packetizer%d_header' % interface), len(h_bytestr), offset=8*offset) == h_bytestr, "Readback failed!"

    def _reorder_channels(self, order, transpose_time=True):
        """
        Reorder the channels such that the channel order[i]
        emerges out of the reorder in position i.
        """
        out_array = np.zeros([self.n_times_per_packet * self.n_ants_per_board * self.n_chans_f // self.n_chans_per_block], dtype='>i2')
        if not transpose_time:
            raise NotImplementedError("Reorder only implemented with time fastest ordering")
        # Check input
        order = np.array(order)
        # We must load the reorder map in one go
        assert order.shape[0] == (self.n_chans_f // self.n_chans_per_block)
        # Start points can only be integer multiples of the number of channels in a word
        for o in order:
            assert o < (self.n_chans_f // self.n_chans_per_block)
            assert o % 1 == 0
        # All elements must appear only once
        assert np.unique(order).shape[0] == order.shape[0]
        serial_chans = self.n_chans_f // self.n_chans_per_block
        for xn, x in enumerate(order):
            #print("Mapping channel %d to position %d" % (x, xn))
            for t in range(self.n_times_per_packet):
                for a in range(self.n_ants_per_board):
                    input_idx = t*self.n_ants_per_board*serial_chans + x*self.n_ants_per_board
                    output_idx = a*serial_chans*self.n_times_per_packet + xn*self.n_times_per_packet + t
                    out_array[output_idx] = input_idx
        
        out_bytes = out_array.tobytes()
        for i in range(len(out_bytes)//4):
            self.fpga.write(self._pipeline_get_regname('chan_reorder_reorder_map'), out_bytes[4*i:4*(i+1)], offset=4*i)
        assert self.fpga.read(self._pipeline_get_regname('chan_reorder_reorder_map'), len(out_bytes)) == out_bytes, "Readback failed"
