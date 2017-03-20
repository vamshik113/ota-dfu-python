import pexpect
import math
import re
import os
import time

from array import array

from util import *

verbose = False

class Procedures:
    CREATE          = 0x01
    SET_PRN         = 0x02
    CALC_CHECKSUM   = 0x03
    EXECUTE         = 0x04
    SELECT          = 0x06
    RESPONSE        = 0x60

    PARAM_COMMAND   = 0x01
    PARAM_DATA      = 0x02

    string_map = {
        CREATE          : "CREATE",
        SET_PRN         : "SET_PRN",
        CALC_CHECKSUM   : "CALC_CHECKSUM",
        EXECUTE         : "EXECUTE",
        SELECT          : "SELECT",
        RESPONSE        : "RESPONSE",
    }

    @staticmethod
    def to_string(proc):
        return Procedures.string_map[proc]

    @staticmethod
    def from_string(proc_str):
        return int(proc_str, 16)

class Results:
    INVALID_CODE                = 0x00
    SUCCESS                     = 0x01
    OPCODE_NOT_SUPPORTED        = 0x02
    INVALID_PARAMETER           = 0x03
    INSUFF_RESOURCES            = 0x04
    INVALID_OBJECT              = 0x05
    UNSUPPORTED_TYPE            = 0x07
    OPERATION_NOT_PERMITTED     = 0x08
    OPERATION_FAILED            = 0x0A

    string_map = {
        INVALID_CODE            : "INVALID_CODE",
        SUCCESS                 : "SUCCESS",
        OPCODE_NOT_SUPPORTED    : "OPCODE_NOT_SUPPORTED",
        INVALID_PARAMETER       : "INVALID_PARAMETER",
        INSUFF_RESOURCES        : "INSUFFICIENT_RESOURCES",
        INVALID_OBJECT          : "INVALID_OBJECT",
        UNSUPPORTED_TYPE        : "UNSUPPORTED_TYPE",
        OPERATION_NOT_PERMITTED : "OPERATION_NOT_PERMITTED",
        OPERATION_FAILED        : "OPERATION_FAILED",
    }

    @staticmethod
    def to_string(res):
        return Results.string_map[res]

    @staticmethod
    def from_string(res_str):
        return int(res_str, 16)


class BleSecureDfuController(object):
    # Class constants
    UUID_BUTTONLESS     = '8e400001-f315-4f60-9fb8-838830daea50'
    UUID_CONTROL_POINT  = '8ec90001-f315-4f60-9fb8-838830daea50'
    UUID_PACKET         = '8ec90002-f315-4f60-9fb8-838830daea50'

    # Class instance variables
    ctrlpt_handle        = 0
    ctrlpt_cccd_handle   = 0
    data_handle          = 0

    pkt_receipt_interval = 5
    pkt_payload_size     = 20

    def __init__(self, target_mac, hexfile_path, datfile_path):
        self.target_mac = target_mac
        
        self.hexfile_path = hexfile_path
        self.datfile_path = datfile_path

        self.ble_conn = pexpect.spawn("gatttool -b '%s' -t random --interactive" % target_mac)
        self.ble_conn.delaybeforesend = 0

    # --------------------------------------------------------------------------
    #  Start the firmware update process
    # --------------------------------------------------------------------------
    def start(self):
        (_, self.ctrlpt_handle, self.ctrlpt_cccd_handle) = self._get_handles(self.UUID_CONTROL_POINT)
        (_, self.data_handle, _) = self._get_handles(self.UUID_PACKET)

        if verbose:
            print 'Control Point Handle: 0x%04x, CCCD: 0x%04x' % (self.ctrlpt_handle, self.ctrlpt_cccd_handle)
            print 'Packet handle: 0x%04x' % (self.data_handle)

        # Subscribe to notifications from Control Point characteristic
        self._enable_notifications(self.ctrlpt_cccd_handle)

        # Set the Packet Receipt Notification interval
        prn = uint16_to_bytes_le(self.pkt_receipt_interval)
        self._dfu_send_command(Procedures.SET_PRN, prn)

        self._dfu_send_init()

        self._dfu_send_image()

    # --------------------------------------------------------------------------
    # Initialize: 
    #    Hex: read and convert hexfile into bin_array 
    #    Bin: read binfile into bin_array
    # --------------------------------------------------------------------------
    def input_setup(self):
        print "Sending file " + os.path.split(self.hexfile_path)[1] + " to " + self.target_mac

        if self.hexfile_path == None:
            raise Exception("input invalid")

        name, extent = os.path.splitext(self.hexfile_path)

        if extent == ".bin":
            self.bin_array = array('B', open(self.hexfile_path, 'rb').read())

            self.hex_size = len(self.bin_array)
            print "Binary imge size: %d" % self.hex_size
            return

        if extent == ".hex":
            intelhex = IntelHex(self.hexfile_path)
            self.bin_array = intelhex.tobinarray()
            self.hex_size = len(self.bin_array)
            print "bin array size: ", self.hex_size
            return

        raise Exception("input invalid")

    # --------------------------------------------------------------------------
    # Perform a scan and connect via gatttool.
    # Will return True if a connection was established, False otherwise
    # --------------------------------------------------------------------------
    def scan_and_connect(self):
        if verbose: print "scan_and_connect"

        print "Connecting to %s" % (self.target_mac) 

        try:
            self.ble_conn.expect('\[LE\]>', timeout=10)
        except pexpect.TIMEOUT, e:
            print "Connect timeout"
            return False

        self.ble_conn.sendline('connect')

        try:
            res = self.ble_conn.expect('.*Connection successful.*', timeout=10)
        except pexpect.TIMEOUT, e:
            print "Connect timeout"
            return False

        return True

    # --------------------------------------------------------------------------
    #  Disconnect from the peripheral and close the gatttool connection
    # --------------------------------------------------------------------------
    def disconnect(self):
        self.ble_conn.sendline('exit')
        self.ble_conn.close()

    def check_DFU_mode(self):
        print "Checking DFU State..."

        self.ble_conn.sendline('characteristics')

        dfu_mode = False

        try:
            self.ble_conn.expect([self.UUID_BUTTONLESS], timeout=2)
        except pexpect.TIMEOUT, e:
            dfu_mode = True

        return dfu_mode

    def switch_to_dfu_mode(self):
        (_, bl_value_handle, bl_cccd_handle) = self._get_handles(self.UUID_BUTTONLESS)

        self._enable_notifications(bl_cccd_handle)

        # Reset the board in DFU mode. After reset the board will be disconnected
        cmd = 'char-write-req 0x%04x 01' % (bl_value_handle)
        self.ble_conn.sendline(cmd)

        # Wait some time for board to reboot
        time.sleep(0.5)

        self.disconnect()

        # Increase the mac address by one and reconnect
        self._target_mac_increase()
        self.ble_conn = pexpect.spawn("gatttool -b '%s' -t random --interactive" % self.target_mac)
        self.ble_conn.delaybeforesend = 0
        return self.scan_and_connect()

    def _target_mac_increase(self):
        parts = list(re.match('(..):(..):(..):(..):(..):(..)', self.target_mac).groups())
        parts[5] = hex(int(parts[5], 16) + 1)
        parts[5] = parts[5][len(parts[5])-2:len(parts[5])].upper()

        # TODO: Handle case where the last byte is FF
        #       Then we need to increase byte 4 as well

        self.target_mac = ':'.join(parts)

    # --------------------------------------------------------------------------
    #  Fetch handles for a given UUID.
    #  Will return a three-tuple: (char handle, value handle, CCCD handle)
    #  Will raise an exception if the UUID is not found
    # --------------------------------------------------------------------------
    def _get_handles(self, uuid):
        self.ble_conn.before = ""
        self.ble_conn.sendline('characteristics')

        try:
            self.ble_conn.expect([uuid], timeout=2)
            handles = re.findall('.*handle: (0x....),.*char value handle: (0x....)', self.ble_conn.before)
            (handle, value_handle) = handles[-1]
        except pexpect.TIMEOUT, e:
            raise Exception("UUID not found: {}".format(uuid))

        return (int(handle, 16), int(value_handle, 16), int(value_handle, 16)+1)

    # --------------------------------------------------------------------------
    #  Wait for notification to arrive.
    #  Example format: "Notification handle = 0x0019 value: 10 01 01"
    # --------------------------------------------------------------------------
    def _dfu_wait_for_notify(self):
        while True:
            if verbose: print "dfu_wait_for_notify"

            if not self.ble_conn.isalive():
                print "connection not alive"
                return None

            try:
                index = self.ble_conn.expect('Notification handle = .*? \r\n', timeout=30)

            except pexpect.TIMEOUT:
                #
                # The gatttool does not report link-lost directly.
                # The only way found to detect it is monitoring the prompt '[CON]'
                # and if it goes to '[   ]' this indicates the connection has
                # been broken.
                # In order to get a updated prompt string, issue an empty
                # sendline('').  If it contains the '[   ]' string, then
                # raise an exception. Otherwise, if not a link-lost condition,
                # continue to wait.
                #
                self.ble_conn.sendline('')
                string = self.ble_conn.before
                if '[   ]' in string:
                    print 'Connection lost! '
                    raise Exception('Connection Lost')
                return None

            if index == 0:
                after = self.ble_conn.after
                hxstr = after.split()[3:]
                handle = long(float.fromhex(hxstr[0]))
                return hxstr[2:]

            else:
                print "unexpeced index: {0}".format(index)
                return None

    # --------------------------------------------------------------------------
    #  Parse notification status results
    # --------------------------------------------------------------------------
    def _dfu_parse_notify(self, notify):
        if len(notify) < 3:
            print "notify data length error"
            return None

        if verbose: print notify

        dfu_notify_opcode = Procedures.from_string(notify[0])
        if dfu_notify_opcode == Procedures.RESPONSE:

            dfu_procedure = Procedures.from_string(notify[1])
            dfu_result  = Results.from_string(notify[2])

            procedure_str = Procedures.to_string(dfu_procedure)
            result_string  = Results.to_string(dfu_result)

            # if verbose: print "opcode: {0}, proc: {1}, res: {2}".format(dfu_notify_opcode, procedure_str, result_string)
            if verbose: print "opcode: 0x%02x, proc: %s, res: %s" % (dfu_notify_opcode, procedure_str, result_string)

            # Packet Receipt notifications are sent in the exact same format
            # as responses to the CALC_CHECKSUM procedure.
            if(dfu_procedure == Procedures.CALC_CHECKSUM and dfu_result == Results.SUCCESS):
                offset = bytes_to_uint32_le(notify[3:7])
                crc32 = bytes_to_uint32_le(notify[7:11])

                return (dfu_procedure, dfu_result, offset, crc32)
            
            elif(dfu_procedure == Procedures.SELECT and dfu_result == Results.SUCCESS):
                max_size = bytes_to_uint32_le(notify[3:7])
                offset = bytes_to_uint32_le(notify[7:11])
                crc32 = bytes_to_uint32_le(notify[11:15])

                return (dfu_procedure, dfu_result, max_size, offset, crc32)

            else:
                return (dfu_procedure, dfu_result)

    # --------------------------------------------------------------------------
    #  Wait for a notification and parse the response
    # --------------------------------------------------------------------------
    def _wait_and_parse_notify(self):
        if verbose: print "Waiting for notification"
        notify = self._dfu_wait_for_notify()

        if verbose: print "Parsing notification"

        result = self._dfu_parse_notify(notify)
        if result[1] != Results.SUCCESS:
            raise Exception("Error in {} procedure, reason: {}".format(
                Procedures.to_string(result[0]),
                Results.to_string(result[1])))

        return result

    # --------------------------------------------------------------------------
    #  Send a procedure + any parameters required
    # --------------------------------------------------------------------------
    def _dfu_send_command(self, procedure, params=[]):
        if verbose: print '_dfu_send_command'

        cmd  = 'char-write-req 0x%04x %02x' % (self.ctrlpt_handle, procedure)
        cmd += array_to_hex_string(params)

        if verbose: print cmd

        self.ble_conn.sendline(cmd)

        # Verify that command was successfully written
        try:
            res = self.ble_conn.expect('Characteristic value was written successfully.*', timeout=10)
        except pexpect.TIMEOUT, e:
            print "State timeout"

    # --------------------------------------------------------------------------
    #  Send an array of bytes
    # --------------------------------------------------------------------------
    def _dfu_send_data(self, data):
        cmd  = 'char-write-cmd 0x%04x' % (self.data_handle)
        cmd += ' '
        cmd += array_to_hex_string(data)

        # if verbose: print cmd

        self.ble_conn.sendline(cmd)

    # --------------------------------------------------------------------------
    #  Enable notifications from the Control Point Handle
    # --------------------------------------------------------------------------
    def _enable_notifications(self, cccd_handle):
        if verbose: print '_enable_notifications'

        cmd  = 'char-write-req 0x%04x %s' % (cccd_handle, '0100')

        if verbose: print cmd

        self.ble_conn.sendline(cmd)

        # Verify that command was successfully written
        try:
            res = self.ble_conn.expect('Characteristic value was written successfully.*', timeout=10)
        except pexpect.TIMEOUT, e:
            print "State timeout"

    # --------------------------------------------------------------------------
    #  Send the Init info (*.dat file contents) to peripheral device.
    # --------------------------------------------------------------------------
    def _dfu_send_init(self):

        if verbose: print "dfu_send_init"

        # Open the DAT file and create array of its contents
        init_bin_array = array('B', open(self.datfile_path, 'rb').read())
        init_size = len(init_bin_array)
        init_crc = 0;

        # Select command
        self._dfu_send_command(Procedures.SELECT, [Procedures.PARAM_COMMAND]);
        (proc, res, max_size, offset, crc32) = self._wait_and_parse_notify()
        
        if offset != init_size or crc32 != init_crc:
            if offset == 0 or offset > init_size:
                # Create command
                self._dfu_send_command(Procedures.CREATE, [Procedures.PARAM_COMMAND] + uint32_to_bytes_le(init_size))
                res = self._wait_and_parse_notify()

            segment_count = 0
            segment_total = int(math.ceil(init_size/float(self.pkt_payload_size)))

            for i in range(0, init_size, self.pkt_payload_size):
                segment = init_bin_array[i:i + self.pkt_payload_size]
                self._dfu_send_data(segment)
                segment_count += 1

                if (segment_count % self.pkt_receipt_interval) == 0:
                    (proc, res, offset, crc32) = self._wait_and_parse_notify()
                    
                    if res != Results.SUCCESS:
                        raise Exception("bad notification status: {}".format(Results.to_string(res)))

            # Calculate CRC
            self._dfu_send_command(Procedures.CALC_CHECKSUM)
            self._wait_and_parse_notify()

        # Execute command
        self._dfu_send_command(Procedures.EXECUTE)
        self._wait_and_parse_notify()

        print "Init packet successfully transfered"

    # --------------------------------------------------------------------------
    #  Send the Firmware image to peripheral device.
    # --------------------------------------------------------------------------
    def _dfu_send_image(self):
        if verbose: print "dfu_send_image"

        # Select Data Object
        self._dfu_send_command(Procedures.SELECT, [Procedures.PARAM_DATA])
        (proc, res, max_size, offset, crc32) = self._wait_and_parse_notify()

        # Split the firmware into multiple objects
        num_objects = int(math.ceil(self.hex_size / float(max_size)))
        print "Max object size: %d, num objects: %d, offset: %d, total size: %d" % (max_size, num_objects, offset, self.hex_size)

        time_start = time.time()
        last_send_time = time.time()

        for j in range((offset/max_size)*max_size, self.hex_size, max_size):
            # print "Sending object {} of {}".format(j/max_size+1, num_objects)

            if offset != self.hex_size:
                if True or offset == 0 or offset > self.hex_size:
                    # Create Data Object
                    size = min(max_size, self.hex_size - j)
                    self._dfu_send_command(Procedures.CREATE, [Procedures.PARAM_DATA] + uint32_to_bytes_le(size))
                    self._wait_and_parse_notify()

                segment_count = 0
                segment_total = int(math.ceil(min(max_size, self.hex_size-j)/float(self.pkt_payload_size)))

                segment_begin = j
                segment_end = min(j+max_size, self.hex_size)

                for i in range(segment_begin, segment_end, self.pkt_payload_size):
                    num_bytes = min(self.pkt_payload_size, segment_end - i)
                    segment = self.bin_array[i:i + num_bytes]
                    self._dfu_send_data(segment)
                    segment_count += 1

                    # print "j: {} i: {}, end: {}, bytes: {}, size: {} segment #{} of {}".format(
                    #     j, i, segment_end, num_bytes, self.hex_size, segment_count, segment_total)

                    if (segment_count % self.pkt_receipt_interval) == 0:
                        (proc, res, offset, crc32) = self._wait_and_parse_notify()
                        
                        if res != Results.SUCCESS:
                            raise Exception("bad notification status: {}".format(Results.to_string(res)))

                        print_progress(offset, self.hex_size, prefix = 'Progress:', suffix = 'Complete', barLength = 50)

                # Calculate CRC
                self._dfu_send_command(Procedures.CALC_CHECKSUM)
                self._wait_and_parse_notify()

            # Execute command
            self._dfu_send_command(Procedures.EXECUTE)
            self._wait_and_parse_notify()

        # Image uploaded successfully, update the progress bar
        print_progress(self.hex_size, self.hex_size, prefix = 'Progress:', suffix = 'Complete', barLength = 50)

        duration = time.time() - time_start
        print "\nUpload complete in {} minutes and {} seconds".format(int(duration / 60), int(duration % 60))