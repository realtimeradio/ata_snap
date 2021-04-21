import casperfpga
import struct
import logging
import numpy as np
import time
from . import ata_snap_fengine

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
    """
    def __init__(self, host, feng_id=0):
        """
        Constructor method
        """
        self.fpga = casperfpga.CasperFpga(host, transport=casperfpga.KatcpTransport)
        self.host = host
        self.logger = logging.getLogger('AtaRfsocFengine')
        self.logger.setLevel(logging.DEBUG)
        self.feng_id = feng_id
        # If the board is programmed, try to get the fpg data
        #if self.is_programmed():
        #    try:
        #        self.fpga.transport.get_meta()
        #    except:
        #        self.logging.warning("Tried to get fpg meta-data from a running board and failed!")

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
        self.fpga.write_int("corr_feng_id", self.feng_id)
