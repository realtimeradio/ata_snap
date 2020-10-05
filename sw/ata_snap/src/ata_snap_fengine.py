import casperfpga
import struct
import logging
import numpy as np
import time

def _ip_to_int(ip):
    """
    convert an IP string (eg '10.11.10.1') to a 32-bit binary
    string, suitable for writing to an FPGA register.
    """
    octets = list(map(int, ip.split('.')))
    ip_int = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
    return ip_int

def silence_tftpy():
    """
    Turn tftpy's logging filter up to logging.CRITICAL,
    to prevent warnings about tftpy transaction retries.
    """
    logs = [
        'tftpy.TftpClient',
        'tftpy.TftpContext',
        'tftpy.TftpPacketFactory',
        'tftpy.TftpPacketTypes',
        'tftpy.TftpServer',
        'tftpy.TftpStates',
        ]
    for log in logs:
        l = logging.getLogger(log)
        l.setLevel(logging.CRITICAL)

class AtaSnapFengine(object):
    """
    This is a class which implements methods for programming
    and communicating with a SNAP board running the ATA F-Engine
    firmware.

    :param host: Hostname of SNAP board associated with this instance.
    :type host: str
    :param ant_id: Antenna ID of the antenna connected to this SNAP.
        This value is used in the output headers of data packets.
    :type ant_id: int
    :param transport: The type of connection the SNAP supports. Should be either
        casperfpga.TapcpTransport (if communicating over 10GbE) or
        casperfpga.KatcpTransport (if communicating via a Raspberry Pi)
    :type transport: casperfpga.Transport
    """
    n_chans_f = 4096 # Number of channels generated by channelizer
    n_chans_out = 2048 # Maximum number of channels output by SNAP
    n_chans_per_block = 16 # Granularity with which we can set channels

    n_chans_per_packet = 256
    def __init__(self, host, ant_id=0, transport=casperfpga.TapcpTransport):
        """
        Constructor method
        """
        self.fpga = casperfpga.CasperFpga(host, transport=transport)
        silence_tftpy()
        self.host = host
        self.logger = logging.getLogger('AtaSnapFengine')
        self.logger.setLevel(logging.DEBUG)
        self.ant_id = ant_id
        # If the board is programmed, try to get the fpg data
        #if self.is_programmed():
        #    try:
        #        self.fpga.transport.get_meta()
        #    except:
        #        self.logging.warning("Tried to get fpg meta-data from a running board and failed!")

    def is_programmed(self):
        """
        Returns True if the fpga appears to be programmed
        with a valid F-engine design. Returns False otherwise.
        The test this method uses is searching for the register
        named `fversion` in the running firmware, so it can
        easily be fooled.
        :return: True if programmed, False otherwise
        :rtype: bool
        """
        if 'fversion' in self.fpga.listdev():
            version = self.fpga.read_uint('fversion')
            self.logger.info("FPGA F-Engine version (based on 'fversion' register) is %d" % version)
            return True
        return False

    def program(self, fpgfile, force=False, init_adc=True):
        """
        Program a SNAP with a new firmware file.

        :param fpgfile: .fpg file containing firmware to be programmed
        :type fpgfile: str
        :param force: If True, overwrite the existing firmware even if the firmware
            to load appears to already be present. This only makes a difference for
            `TapcpTransport` connections.
        :type force: bool
        :param init_adc: If True, initialize the ADC cards after programming. If False,
            you *must* do this manually before using the firmware using the
            `adc_initialize` method.
        :type init_adc: bool
        """
        # in an abuse of the casperfpga API, only the TapcpTransport has a "force" option
        if isinstance(self.fpga.transport, casperfpga.TapcpTransport):
            self.fpga.transport.upload_to_ram_and_program(fpgfile, force=force)
        else:
            self.fpga.upload_to_ram_and_program(fpgfile)
        self.fpga.get_system_information(fpgfile)
        if init_adc:
            self.adc_initialize()

    def adc_initialize(self):
        """
        Initialize the ADC interface by performing FPGA<->ADC link training.
        Put the ADC chip in dual-input mode.
        This method must be called after programming a SNAP, and is called
        automatically if using this class's `program` method with init_adc=True.
        """
        import adc5g
        self.logger.info("Configuring ADC->FPGA interface")
        chosen_phase, glitches = adc5g.calibrate_mmcm_phase(self.fpga, 0, ['ss_adc'])
        self.logger.info("Glitches-vs-capture phase: %s" % glitches)
        self.logger.info("Chosen phase: %d" % chosen_phase)
        self.logger.info("Configuring ADCs for dual-input mode")
        adc5g.spi.set_spi_control(self.fpga, 0, adcmode=0b0100, stdby=0, dmux=1, bg=1, bdw=0b11, fs=0, test=0)

    def adc_get_samples(self):
        """
        Get a block of samples from both ADC inputs, captured simultaneously.

        :return: x, y (numpy arrays of ADC sample values)
        :rtype: numpy.ndarray
        """
        d, t = self.fpga.snapshots.ss_adc.read_raw(man_trig=True, man_valid=True)
        d_unpacked = np.fromstring(d['data'], dtype=np.int8)
        x = d_unpacked[0::2]
        y = d_unpacked[1::2]
        return x, y

    def adc_get_stats(self, per_core=False):
        """
        Get the mean value and power, and a count of overflow events for the system's ADCs. Statistics
        are calculated over the last 512k samples, and are computed from samples obtained from all ADC
        channels simultaneously.

        :param per_core: If True, return stats for each ADC core. If false, return stats for each ADC channel.
        :type per_core: bool
        :returns: A 3-tuple of numpy.ndarray, with either 4 entries (if per_core=True) or 2 entries (if per_core=False).
            The tuple is (clip_count, mean, mean_power) where clip_count is the number of clipping events in the last
            512k samples, mean is the average of the last 64k samples, and mean_power is the mean power of the last
            512k samples.
            If per_core=True, each array has 4 entries, representing the four ADC cores. Cores 0, 2 digitize the X-pol
            RF input, and cores 1, 3 digitize the Y-pol input.
            If per_core=False, each array has 2 entries, with the first address the X-pol RF input, and the second the Y-pol.
        :rtype: (numpy.ndarray, np.ndarray, np.ndarray)
        """
        # First enable the capture
        self.fpga.write_int("stats_enable", 1)
        # Wait for a capture period. 512k samples is <10ms for even slowish clock rates
        time.sleep(0.01)
        # Disable capture
        self.fpga.write_int("stats_enable", 0)
        # Read bram
        # 4 x 32bit values per word (one is a dummy); 16 words
        x = struct.unpack(">64l", self.fpga.read("stats_levels", 4*4*16))
        if per_core:
            n = 4
        else:
            n = 2
        clip_count = np.array(x[1::4]).reshape([16//n, n]).sum(axis=0)
        mean = np.array(x[2::4]).reshape([16//n, n]).mean(axis=0)
        mean_pow= np.array(x[3::4]).reshape([16//n, n]).mean(axis=0)
        return clip_count, mean, mean_power

    def sync_wait_for_pps(self):
        """
        Block until an external PPS trigger has passed.
        I.e., poll the FPGA's PPS count register and do not
        return until is changes.
        """
        self.logger.info('Waiting for PPS to pass')
        count_now = self.sync_get_ext_count()
        while (self.sync_get_ext_count() == count_now):
            time.sleep(0.05)

    def sync_arm(self):
        """
        Arm the FPGA's sync generators for triggering on a 
        subsequent PPS.
        The arming proceedure is the following:
        1. Wait for a PPS to pass using `sync_wait_for_pps`.
        2. Arm the FPGA's sync register to trigger on the next+2 PPS
        3. Compute the time this PPS is expected, based on this computer's clock.
        4. Write this time as a 32-bit UNIX time integer to the FPGA, to record
        the sync event.

        :return: Sync trigger time, in UNIX format
        :rval: int
        """
        self.logger.info('Issuing sync arm')
        self.fpga.write_int('sync_arm', 0)
        self.fpga.write_int('sync_arm', 1)
        self.fpga.write_int('sync_arm', 0)
        sync_time = int(np.ceil(time.time())) + 2
        self.fpga.write_int('sync_sync_time', sync_time)
        return sync_time

    def sync_get_last_sync_time(self):
        """
        Get the sync time currently stored on this FPGA

        :return: Sync trigger time, in UNIX format
        :rval: int
        """
        return self.fpga.read_uint('sync_sync_time')

    def sync_get_adc_clk_freq(self):
        """
        Infer the ADC clock period by counting FPGA clock ticks
        between PPS events.

        :return: ADC clock rate in MHz
        :rval: float
        """
        adc_count = 8 * self.sync_get_fpga_clk_pps_interval()
        freq_mhz = adc_count / 1.0e6
        return freq_mhz

    def sync_get_ext_count(self):
        """
        Read the number of external sync pulses which have been received since
        the board was last programmed.

        :return: Number of sync pulses received
        :rval: int
        """
        return self.fpga.read_uint('sync_count')

    def sync_get_fpga_clk_pps_interval(self):
        """
        Read the number of FPGA clock ticks between the last two external sync pulses.

        :return: FPGA clock ticks
        :rval: int
        """
        return self.fpga.read_uint('sync_period')

    def _sync_set_period(self, period):
        """
        Set the period, in FPGA clock ticks, of the internal sync pulse generation logic.
        This period should be divisible by both 6 (an esoteric firmware requirement)
        and the number of points in the design's FFT, and is used to define the accumulation
        length of the firmware's spectrometer mode. This method should be called
        only via `set_accumulation_length`.

        :param period: Number of FPGA clock ticks in a synchronization period.
        :type period: int
        :raises ValueError: If the chosen sync period is not allowed.
        """
        self.logger.info("Setting sync period to %d FPGA clocks" % period)
        # If there is a valid clock and PPS connected, we can turn this into a time
        clocks_per_sec = self.sync_get_fpga_clk_pps_interval()
        sync_period_ms = 1000*period / float(clocks_per_sec)
        self.logger.info("Based on the PPS input, sync period is %.2f milliseconds" % sync_period_ms)
        if period % (2*self.n_chans_f):
            self.logger.warning("Sync period %d is not compatible with FFT length %d" % (period, 2*self.n_chans_f))
            raise ValueError("Sync period %d is not compatible with FFT length %d" % (period, 2*self.n_chans_f))
        if period % 6:
            self.logger.warning("Sync period %d is not compatible with voltage output reordering." % (period))
            self.logger.warning("Sync period should be a multiple of 6")
            raise ValueError("Sync period should be a multiple of 6")
        self.fpga.write_int('timebase_sync_period', period)

    def set_accumulation_length(self, acclen):
        """
        Set the number of spectra to accumulate for the on-board
        spectrometer.

        :param acclen: Number of spectra to accumulate
        :type acclen: int
        """
        self.logger.info('Setting accumulation length to %d spectra' % acclen)
        self._sync_set_period(acclen * self.n_chans_f * 2 // 8) # *2 for real-FFT; /8 for ADC demux

    #def _assign_channel(self, in_num, out_num):
    #    """
    #    Reorder the channels such that the `out_num`th channel
    #    out of the reorder block is channel `in_num`.
    #    """
    #    self.fpga.write_int('chan_reorder_chan_remap_map', in_num, word_offset=out_num)

    #def _assign_channels(self, in_nums, out_num_start):
    #    """
    #    Reorder the channels such that the `out_num + i`th channel
    #    out of the reorder block is channel `in_num` + i.
    #    """
    #    in_nums_str = struct.pack('>L', *in_nums)
    #    self.fpga.write('chan_reorder_chan_remap_map', in_nums_str, offset=out_num_start*4)

    #def fft_set_shift(self, shift=0b0011111100000):
    #    """
    #    Set the FFT shift pattern.
    #    The firmware interprets the shift value as a binary value, with
    #    each bit controlling the shift (divide-by-two) at one stage of
    #    the FFT. The number of stages in the FFT is equal to log2(FFT_SIZE).

    #    Example usage:
    #        `fft_set_shift(2**13-1)` : Shift down every stage of an 8k-point FFT
    #        `fft_set_shift(0b11)` : Shift down on the first two stages of the FFT only
    #        `fft_set_shift(0)` : Don't shift at any stage of the FFT
    #    
    #    The necessity for shifting depends on the input power levels into the FFT,
    #    the number of bits in the FFT data path, and the nature of the input signal.
    #    Sinusoidal input signals grow by a factor of 2 at each FFT stage, and therefore
    #    might need to be shifted every stage.
    #    Noise-like signals grow by a factor of sqrt(2) at each FFT stage, and therefore
    #    might only needed to be shifted every other stage.
    #    Setting the FFT shift should be done in concert with monitoring the FFT overflow
    #    state with `fft_of_detect`.

    #    NB: in firmware versions >=1.02 the FFT input data are padded by 7 bits. For an
    #    8192 point transform, this means 6 bits of shifting is sufficient to avoid
    #    overflow.

    #    :param shift: Shift schedule
    #    :type shift: int
    #    """
    #    self.logger.info('Setting FFT shift to 0x%x' % shift)
    #    self.fpga.write_int('pfb_fft_shift', shift)

    def fft_of_detect(self):
        """
        Read the FFT overflow detection register. Will return True if
        an overflow has been detected in the last accumulation period. False otherwise.
        Increase the FFT shift schedule to avoid persistent overflows.

        :return: True if FFT overflowed in the last accumulation period, False otherwise.
        :rtype: bool
        """
        return bool(self.fpga.read_uint('pfb_fft_of'))

    def fft_cast_of_detect(self):
        """
        Read the FFT's cast overflow detection register. Will return True if
        an overflow has been detected in the last accumulation period. False otherwise.
        Increase the FFT shift schedule to avoid persistent overflows.

        FFT processing pads 18-bit input data with 7 guard bits (to reach 25 bits), performs
        an FFT with a 25-bit data path, and then throws away the top 7 bits to retain 18 bits
        of data.
        In the process of this bit truncation, data may overflow. Unlike an internal FFT overflow,
        which corrupts an entire spectrum, an overflow during casting simply corrupts the channel
        with the overflow. Since this is likely to be a bin containing RFI, this may be acceptable,
        but you should check the spectrometer spectra to ensure the majority of the spectrum remains
        intact.

        :return: True if post-FFT cast overflowed in the last accumulation period, False otherwise.
        :rtype: bool
        """
        return bool(self.fpga.read_uint('pfb_cast_overflow'))

    def quant_spec_read(self, mode="auto"):
        """
        Read a single accumulated spectrum of the 4-bit quantized data/

        :param mode: "auto" to read an autocorrelation for each of the X and Y pols.
            "cross" to read a cross-correlation of Xconj(Y).
        :type mode: str:
        :raises AssertionError: if mode is not "auto" or "cross"
        :return: If mode="auto": A tuple of two numpy arrays, xx, yy, containing
            a power spectrum from the X and Y polarizations.
            If mode="cross": A complex numpy array containing the cross-power
            spectrum of Xconj(Y).
        :rtype: numpy.array
        """
        assert mode in ["auto", "cross"]
        if mode == "auto":
            self.fpga.write_int("corr_vacc_ss_sel", 0)
        else:
            self.fpga.write_int("corr_vacc_ss_sel", 1)

        self.fpga.snapshots.corr_vacc_ss_ss0.arm() # This arms all RAMs
        d0, t0 = self.fpga.snapshots.corr_vacc_ss_ss0.read_raw(arm=False)
        d1, t1 = self.fpga.snapshots.corr_vacc_ss_ss1.read_raw(arm=False)
        d0i = struct.unpack(">%di" % (d0["length"] // 4), d0["data"])
        d1i = struct.unpack(">%di" % (d1["length"] // 4), d1["data"])
        if mode == "auto":
            xx_0  = d0i[0::2]
            xx_1  = d1i[0::2]
            yy_0  = d0i[1::2]
            yy_1  = d1i[1::2]
            xx = np.zeros(self.n_chans_f)
            yy = np.zeros(self.n_chans_f)
            for i in range(self.n_chans_f // 2):
                xx[2*i]   = xx_0[i]
                xx[2*i+1] = xx_1[i]
                yy[2*i]   = yy_0[i]
                yy[2*i+1] = yy_1[i]
            return xx, yy
        elif mode == "cross":
            xy_0_r = d0i[0::2]
            xy_0_i = d0i[1::2]
            xy_1_r = d1i[0::2]
            xy_1_i = d1i[1::2]
            xy = np.zeros(self.n_chans_f, dtype=np.complex)
            for i in range(self.n_chans_f // 2):
                xy[2*i]   = xy_0_r[i] + 1j*xy_0_i[i]
                xy[2*i+1] = xy_1_r[i] + 1j*xy_1_i[i]
            return xy

    def eq_load_coeffs(self, pol, coeffs):
        """
        Load coefficients with which to multiply data prior to 4-bit quantization.
        Coefficients are rounded and saturated such that they fall in the range (0, 2048),
        with a precision of 2**-5 = 0.03125.
        A single coefficient can be provided, in which case coefficients for all frequency
        channels will be set to this value.
        If an array or list of coefficients are provided, there should be one coefficient
        per frequency channel in the firmware pipeline.

        :param pol: Selects which polarization vectors are being loaded to (0 or 1)
            0 is the first ADC input, 1 is the second.
        :type pol: int
        :param coeffs: The coefficients to load. If `coeffs` is a single number, this value
            is loaded as the coefficient for all frequency channels. If `coeffs`
            is an array or list, it should have length self.n_chans_f. Element [i]
            of this vector is the coefficient applied to channel i.
            Coefficients are quantized to UFix16_5 precision.
        :type coeffs: float, or list / numpy.ndarray
        :raises AssertionError: If an array of coefficients is provided with an invalid size,
            if any coefficients are negative, or if pol is a non-allowed value
        """
        COEFF_BITS = 32 # Bits per coefficient
        COEFF_BP = 5 # binary point position

        assert pol in [0, 1]
        # If the coefficients provided are a single number
        # set all coefficients to this value
        try:
            coeff = float(coeffs)
            coeffs = [coeff for _ in range(self.n_chans_f)]
        # Otherwise force numpy array to list
        except TypeError:
            coeffs = list(coeffs)
            assert len(coeffs) == self.n_chans_f
        # Negative equalization coefficients don't make sense!
        for coeff in coeffs:
            assert coeff >= 0
        # Manipulate scaling  so that we can write an integer which
        # will be interpreted as a UFix16_5 number.
        coeffs = [min(2**COEFF_BITS - 1, int(c*COEFF_BP)) for c in coeffs] # scale up by binary point and saturate
        if COEFF_BITS == 8:
            coeffs_str = struct.pack('>%dB'%self.n_chans_f, *coeffs)
        elif COEFF_BITS == 16:
            coeffs_str = struct.pack('>%dH'%self.n_chans_f, *coeffs)
        elif COEFF_BITS == 32:
            coeffs_str = struct.pack('>%dL'%self.n_chans_f, *coeffs)
        else:
            raise TypeError("Don't know how to convert %d-bit numbers to binary" % COEFF_BITS)
        self.fpga.write('eq_pol%d_coeffs' % pol, coeffs_str)
        

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
        self.fpga.write('eqtvg_pol%d_tv' % pol, tv_8bit_str)

    def eq_test_vector_mode(self, enable):
        """
        Turn on or off the test vector mode downstream of the 4-bit
        quantizers. This mode can be used to replace the
        FFT output in the voltage data path with an arbitrary pattern which can
        be set with `eq_load_test_vectors`

        :param enable: True to turn on the test mode, False to turn off
        :type enable: bool
        """
        if enable:
            self.logger.info("Turning ON post-EQ test-vectors")
        else:
            self.logger.info("Turning OFF post-EQ test-vectors")
        self.fpga.write_int('eqtvg_tvg_en', int(enable))

    def spec_test_vector_mode(self, enable):
        """
        Turn on or off the test vector mode in the spectrometer data path.
        This mode replaces the FFT output in the data path with 12 bit counter
        which occupies the most significant bits of the imaginary part of the FFT
        output.
        I.e. when enabled, the imaginary part of each spectrum is a ramp from
        0..4095 / 2**17

        :param enable: True to turn on the test mode, False to turn off
        :type enable: bool
        """
        if enable:
            self.logger.info("Turning ON Spectrometer test-vectors")
        else:
            self.logger.info("Turning OFF Spectrometer test-vectors")
        self.fpga.write_int('spec_tvg_tvg_en', int(enable))

    def spec_read(self, mode="auto"):
        """
        Read a single accumulated spectrum.

        :param mode: "auto" to read an autocorrelation for each of the X and Y pols.
            "cross" to read a cross-correlation of Xconj(Y).
        :type mode: str:
        :raises AssertionError: if mode is not "auto" or "cross"
        :return: If mode="auto": A tuple of two numpy arrays, xx, yy, containing
            a power spectrum from the X and Y polarizations.
            If mode="cross": A complex numpy array containing the cross-power
            spectrum of Xconj(Y).
        :rtype: numpy.array
        """
        assert mode in ["auto", "cross"]
        if mode == "auto":
            self.fpga.write_int("corr_vacc_ss_sel", 0)
        else:
            self.fpga.write_int("corr_vacc_ss_sel", 1)

        self.fpga.snapshots.corr_vacc_ss_ss0.arm() # This arms all RAMs
        d0, t0 = self.fpga.snapshots.corr_vacc_ss_ss0.read_raw(arm=False)
        d1, t1 = self.fpga.snapshots.corr_vacc_ss_ss1.read_raw(arm=False)
        d2, t2 = self.fpga.snapshots.corr_vacc_ss_ss2.read_raw(arm=False)
        d3, t3 = self.fpga.snapshots.corr_vacc_ss_ss3.read_raw(arm=False)
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
            xx = np.zeros(self.n_chans_f)
            yy = np.zeros(self.n_chans_f)
            for i in range(self.n_chans_f // 4):
                xx[4*i]   = xx_0[i]
                xx[4*i+1] = xx_1[i]
                xx[4*i+2] = xx_2[i]
                xx[4*i+3] = xx_3[i]
                yy[4*i]   = yy_0[i]
                yy[4*i+1] = yy_1[i]
                yy[4*i+2] = yy_2[i]
                yy[4*i+3] = yy_3[i]
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
            return xy

    def spec_plot(self, mode="auto"):
        """
        Plot an accumulated spectrum using the matplotlib library.
        Frequency axis is infered from the ADC clock frequency detected with
        `sync_get_adc_clk_freq`.

        :param mode: "auto" to plot a power spectrum from the X and Y
            polarizations on separate subplots.
            "cross" to plot the magnitude and phase of a complex-valued
            cross-power spectrum of the two polarizations.
        :type mode: str:
        :raises AssertionError: if mode is not "auto" or "cross"
        """
        from matplotlib import pyplot as plt
        assert mode in ["auto", "cross"]
        freq_range = np.linspace(0, self.sync_get_adc_clk_freq() / 2, self.n_chans_f + 1)[0:-1]
        if mode == "auto":
            self.logger.info("Grabbing auto-correlation spectra")
            x, y = self.spec_read(mode=mode)
            self.logger.info("Plotting spectra")
            plt.figure()
            plt.subplot(2,1,1)
            plt.title("XX")
            plt.semilogy(freq_range, x)
            plt.ylabel('Power [arb ref]')
            plt.xlabel('Frequency [MHz]')
            plt.subplot(2,1,2)
            plt.title("YY")
            plt.semilogy(freq_range, y)
            plt.ylabel('Power [arb ref]')
            plt.xlabel('Frequency [MHz]')
            plt.show()
        elif mode == "cross":
            self.logger.info("Grabbing auto-correlation spectrum")
            xy = self.spec_read(mode=mode)
            self.logger.info("Plotting spectra")
            plt.figure()
            plt.subplot(2,1,1)
            plt.title("abs(X*Y)")
            plt.semilogy(freq_range, np.abs(xy))
            plt.ylabel('Power [arb ref]')
            plt.xlabel('Frequency [MHz]')
            plt.subplot(2,1,2)
            plt.title("angle(X*Y)")
            plt.plot(freq_range, np.angle(xy))
            plt.ylabel('Phase [radians]')
            plt.xlabel('Frequency [MHz]')
            plt.show()

    def spec_set_destination(self, dest_ip):
        """
        Set the destination IP address for spectrometer packets.

        :param dest_ip: Destination IP address. E.g. "10.0.0.1"
        :type dest_ip: str
        """
        self.logger.info('Setting spectrometer packet destination to %s' % dest_ip)
        ip_int = _ip_to_int(dest_ip)
        self.fpga.write_int("corr_dest_ip", ip_int)

    def eth_set_mode(self, mode="voltage"):
        """
        Set the 10GbE output stream to either
        "voltage" or "spectra" mode.
        To prevent undesired behaviour, this method will
        disable Ethernet transmission prior to switching. Transmission
        should be re-enabled if desired using `eth_enable_output`.

        :param mode: "voltage" or "spectra"
        :type mode: str
        :raises AssertionError: If mode is not an allowed value
        """
        assert mode in ["voltage", "spectra"]
        # Disbale the ethernet output before doing anything
        self.eth_enable_output(enable=False)
        if mode == "voltage":
             self.fpga.write_int("eth_mux_use_voltage", 1)
        elif mode == "spectra":
             self.fpga.write_int("eth_mux_use_voltage", 0)

    def eth_enable_output(self, enable=True):
        """
        Enable the 10GbE output datastream. Only do this
        after appropriately setting an output configuration and
        setting the pipeline mode with `eth_set_mode`.
        For spectra mode, prior to enabling Ethernet the destination
        address should be set with `spec_set_destination`.
        For voltage mode, prior to enabling Ethernet configuration should
        be loaded with `select_output_channels`

        :param enable: Set to True to enable Ethernet transmission, or False to disable.
        :type enable: bool
        """
        ENABLE_MASK =  0x00000002
        v = self.fpga.read_uint("eth_ctrl")
        v = v &~ ENABLE_MASK
        if enable:
            v = v | ENABLE_MASK
        self.fpga.write_int("eth_ctrl", v)

    def eth_reset(self):
        """
        Reset the Ethernet core. This method will clear the reset after asserting,
        and will leave the transmission stream disabled.
        Reactivate the Ethernet core with `eth_enable_output`
        """
        RST_MASK = 0x00040001 # both stats and core resets
        self.eth_enable_output(enable=False)
        v = self.fpga.read_uint("eth_ctrl")
        v = v | RST_MASK
        self.fpga.write_int("eth_ctrl", v)
        v = v &~ RST_MASK
        self.fpga.write_int("eth_ctrl", v)

    def eth_print_counters(self):
        """
        Print ethernet statistics counters.
        This is a simple wrapper around casperfpgas gbes.read_counters() method.
        """
        print(self.fpga.gbes.eth_core.read_counters())

    def eth_set_dest_port(self, port):
        """
        Set the destination UDP port for output 10GbE packets.

        :param port: UDP port to which traffic should be sent.
        :type port: int
        """
        PORT_MASK = (0xffff << 2)
        v = self.fpga.read_uint("eth_ctrl")
        v = v &~ PORT_MASK
        v = v | (port << 2)
        self.fpga.write_int("eth_ctrl", v)

    #def set_dest_mac(self, ip, mac):
    #    """
    #    Set the MAC address of a given IP.

    #    Inputs:
    #        ip [str]  : IP address of ARP entry. Eg. '10.0.1.123'
    #        mac [int] : MAC address of ARP entry. Eg. 0x020304050607
    #    """

    def select_output_channels(self, start_chan, n_chans, dests=['0.0.0.0']):
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

        :raises AssertionError: If the following conditions aren't met:
            `start_chan` should be a multiple of self.n_chans_per_block (16)
            `n_chans` should be a multiple of self.n_chans_per_packet (256)
            `n_chans` should be <= self.n_chans_out (2048)
        """

        ant_id = self.ant_id

        assert start_chan % self.n_chans_per_block == 0
        assert n_chans % self.n_chans_per_packet == 0
        assert n_chans <= self.n_chans_out
        assert start_chan + n_chans <= self.n_chans_f
        # Can't sent to more destinations than we have packets-per-spectrum
        n_dests = len(dests)
        assert n_dests <= n_chans // self.n_chans_per_packet 
        # Require that traffic is spread over destinations in a balanced fashion
        assert (n_chans // self.n_chans_per_packet) % n_dests == 0
        n_slots_per_dest = (n_chans // self.n_chans_per_packet) // n_dests

        self.logger.info('Number of destinations: %d' % n_dests)
        self.logger.info('Number of slots per destination: %d' % n_slots_per_dest)

        # Attempt to send these channels at regularly spaced intervals
        n_available_slots = self.n_chans_out // self.n_chans_per_packet
        n_required_slots  = n_chans // self.n_chans_per_packet
        n_spare_slots = n_available_slots - n_required_slots

        self.logger.info('Available slots: %s' % n_available_slots)
        self.logger.info('Required slots: %s' % n_required_slots)
        self.logger.info('Spare slots: %s' % n_spare_slots)
        # Number of used slots in a row which we can follow with a dummy slot
        # This will never generate more than 1 unused slot per used slot, but this
        # is fine, if not optimal to minimize traffic burstiness
        if n_spare_slots == 0:
            n_slots_req_per_spare = n_required_slots
        else:
            n_slots_req_per_spare = int(np.ceil(n_required_slots / n_spare_slots))

        self.logger.info('Number of used consecutive used slots: %s' % n_slots_req_per_spare)

        slot_chan = []
        slot_is_valid = []
        slot_dest = []
        slot_start_chan = start_chan
        n_chans_assigned = 0
        n_slots_assigned = 0
        sn = 0
        dest_slot_cnt = 0
        for slot in range(n_available_slots):
            # Every block of n_slots_req_per_spare valid blocks, insert a dummy
            if sn == n_slots_req_per_spare:
                slot_chan += [0]
                slot_is_valid += [False]
                slot_dest += ['0.0.0.0'] # firmware interprets as "don't send"
                sn = 0
                continue
            # Deal with unused slots at the end
            if n_chans_assigned >= n_chans:
                slot_chan += [0]
                slot_is_valid += [False]
                slot_dest += ['0.0.0.0'] # firmware interprets as "don't send"
                continue
            slot_chan += [slot_start_chan]
            slot_is_valid += [True]
            slot_dest += [dests[n_slots_assigned // n_slots_per_dest]]
            slot_start_chan += self.n_chans_per_packet
            n_chans_assigned += self.n_chans_per_packet
            n_slots_assigned += 1
            sn += 1

        # Now reorder channels and set output headers appropriately
        for slot in range(n_available_slots):
            sc = slot_chan[slot]
            self.logger.info("Sending slot %d to %s (start channel %d)" % (slot, slot_dest[slot], sc))
            self.fpga.write_int('packetizer_ants', self.ant_id, word_offset=slot)
            self.fpga.write_int('packetizer_ips', _ip_to_int(slot_dest[slot]), word_offset=slot)
            self.fpga.write_int('packetizer_chans', sc, word_offset=slot)
            if not slot_is_valid[slot]:
                self._assign_chans(range(self.n_chans_per_packet), slot*2*self.n_chans_per_packet)
            else:
                self._assign_chans(range(sc, sc + self.n_chans_per_packet), slot*2*self.n_chans_per_packet)

    def _assign_chans(self, channel_range, start_index):
        """
        Reorder channels such that channel_range[i] takes index start_index+i

        Example usage:
            Move channels 0..15 to the middle of the band
                _assign_chans(range(16), 4096)
            Move channels 12,13,14,15,0,1,2,3 to the start of the band
                _assign_chans([12,13,14,15,0,1,2,3], 0)

        `channel_range` must be a multiple of 4 channels long, in contiguous blocks
        of 4 channels. Eg. [0 1 2 3, 12 13 14 15] is OK, but [0, 1, 2, 3, 14, 15, 16, 17] is not.
        `start_index` must be a multiple of 4.

        :param channel_range: Input channel order.
        :type channel_range: list of ints
        :param start_index:
        :type start_index: int
        :raises AssertionError: If above conditions on `channel_range` and `start_index` are not met.
        """
        assert len(channel_range) % 4 == 0
        assert start_index % 4 == 0
        self.logger.info("Reordering channels %s to start at index %d" % (channel_range, start_index))
        channel_range = [x//4 for x in channel_range[0::4]]
        channel_range_str = struct.pack('>%dH' % (len(channel_range)), *channel_range)
        start_index = start_index // 4
        # Write at offset 2*start_index, since each index is two bytes in memory
        write_offset = start_index * 2
        print(len(channel_range_str), write_offset)
        assert write_offset % 4 == 0, 'Attempted write incompatible with 32-bit word boundaries'
        self.fpga.write("chan_reorder_reorder3_map1", channel_range_str, offset=write_offset)
