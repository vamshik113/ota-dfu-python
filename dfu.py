#!/usr/bin/env python

from __future__ import print_function

import argparse
import os
import re
import sys

import util

from ble_secure_dfu_controller import BleDfuControllerSecure
from ble_legacy_dfu_controller import BleDfuControllerLegacy
from unpacker import Unpacker


def main():
    purpose = 'Support for Over The Air (OTA) Device Firmware Update (DFU) ' \
              'process of Nordic Semiconductor nRF5 (nRF51 or nRF52) based ' \
              'Bluetooth Low Energy (BLE) peripherals.'
    parser = argparse.ArgumentParser(description=purpose)
    parser.add_argument(
        '--address', '-a',
        dest="address",
        required=True,
        help="target address of DFU capable device, "
             "like: 'DE:AD:BE:EF:01:02' or 'deadbeef0102'"
    )
    parser.add_argument(
        '--file', '-f',
        dest="hex_file",
        help='the .hex file to be uploaded'
    )
    parser.add_argument(
        '--dat', '-d',
        dest="dat_file",
        help='the .dat file to be uploaded'
    )
    parser.add_argument(
        '--zip', '-z',
        dest="zip_file",
        help='the .zip file to be used (with .bin / .dat files)'
    )
    parser.add_argument(
        '--legacy',
        dest="secure_dfu",
        action='store_false',
        help='use legacy bootloader (Nordic SDK < 12)'
    )
    parser.add_argument(
        '--secure',
        dest="secure_dfu",
        action='store_true',
        help='use secure bootloader (Nordic SDK >= 12)'
    )
    args = parser.parse_args()

    # ensure a proper formatted address
    mac_address = util.normalize_address(args.address)
    if not mac_address:
        print("Incorrect MAC-address '{}'".format(args.address))
        sys.exit(2)

    # determine the actual firmware files to use
    unpacker = Unpacker()
    hex_fname = args.hex_file or ''
    dat_fname = args.dat_file or ''
    if args.zip_file:
        if args.hex_file or args.dat_file:
            print("Conflicting input directives, too many files specified.")
            sys.exit(2)
        try:
            hex_fname, dat_fname = unpacker.unpack_zipfile(args.zip_file)
        except Exception as err:
            print(err)
    elif (not args.hex_file) or (not args.dat_file):
        print("Missing input directives, too few files specified.")
        sys.exit(2)

    # check that files exist
    if not os.path.isfile(hex_fname):
        print("Error: .hex file '{}' doesn't exist".format(hex_fname))
        exit(2)
    if not os.path.isfile(dat_fname):
        print("Error: .dat file '{}' doesn't exist".format(dat_fname))
        exit(2)

    # initialize the DFU handler to use
    if args.secure_dfu:
        ble_dfu = BleDfuControllerSecure(mac_address, hex_fname, dat_fname)
    else:
        ble_dfu = BleDfuControllerLegacy(mac_address, hex_fname, dat_fname)

    try:
        # initialize inputs
        ble_dfu.input_setup()

        # connect to peripheral; assume application mode
        if ble_dfu.scan_and_connect():
            if not ble_dfu.check_DFU_mode():
                print("Need to switch to DFU mode")
                success = ble_dfu.switch_to_dfu_mode()
                if not success:
                    print("Couldn't reconnect")
        else:
            # the device might already be in DFU mode (MAC + 1)
            ble_dfu.target_mac_increase(1)
            # try connection with new address
            print("Couldn't connect, will try DFU MAC")
            if not ble_dfu.scan_and_connect():
                raise Exception("Can't connect to device")

        # perfom the DFU process
        ble_dfu.start()

        # disconnect from peer device if not done already and clean up
        ble_dfu.disconnect()

    except Exception as err:
        print("Exception at line {}: {}".format(
            sys.exc_info()[2].tb_lineno, err))
        pass

    # if Unpacker for zipfile used then delete Unpacker
    if unpacker:
        unpacker.delete()

    print("Done.")


if __name__ == '__main__':
    main()
