Python nRF52 DFU Server
============================

A python script for bluez gatttool using pexpect to achive Device Firmware Updates (DFU) to the nRF52.  
The host system is assumed to be some flavor of Linux, and was developed with the Raspberry-Pi as the primary hosting system.

**NOTE:**   
This is probably not a beginner's project.  
Peripheral firmware updating is a complex process, requiring several critical development support steps, not covered here, before the *dfu.py* utility can be used.

It is assumed that your peripheral firmware has been build to Nordic's SDK8.x + SoftDevice 8.x  
The target peripheral firmware should also include some variation of Nordic's DFU support.

How you get the target periheral to enter DFU-mode (e.g. advertizing *DfuTarg*) is not handled here.    
It is assumed you can trigger your peripheral to enter the bootloader; either by a hardware switch or application-trigger.

The *dfu.py* utility comes into play only after the peripheral is executing the bootloader.

System:
* Ubuntu 14.04
* Asus X550LD (With integrated Bluetooth 4.0 interface)
* bluez - 5.4 or later

This project assumes you are developing on a Linux/Unix or OSX system and deploying to a Linux system. 

Prerequisite
------------

    sudo pip install pexpect
    sudo pip install intelhex

Firmware Build Requirement
--------------------------
* Your nRF52 firmware build method will produce either a firmware hex or bin file named *application.hex* or *application.bin*.  This naming convention is per Nordics DFU specification, which is use by this DFU server as well as the Android Master Control Panel DFU, and iOS DFU app.  
* Your nRF52 firmware build method will produce an Init file (aka *application.dat*).  Again, this is per Nordic's naming conventions. 

The *nrfutil* Utility
---------------------
https://github.com/NordicSemiconductor/pc-nrfutil/tree/0_5_1

The nrfutil utility will read your build method's hex file and produce a zip file. Ideally, you would incorporate the nrfutil utility into your build system so that your build method will generate the dat file for each build.  

nrfutil dfu genpkg app_package.zip --application application.hex

Usage
-----
There are two ways to speicify firmware files for this OTA-DFU server. Either by specifying both the <hex or bin> file with the dat file, or more easily by the zip file, which contains both the hex and dat files.  
The new "zip file" form is encouraged by Nordic, but the older hex+dat file methods should still work.  


Usage Examples
--------------

    > sudo ./dfu.py -f ~/application.hex -d ~/application.dat -a EF:FF:D2:92:9C:2A

or

    > sudo ./dfu.py -z ~/application.zip -a EF:FF:D2:92:9C:2A  

To figure out the address of DfuTarg do a 'hcitool lescan' - 

    $ sudo hcitool -i hci0 lescan  
    LE Scan ...   
    CD:E3:4A:47:1C:E4 DfuTarg  
    CD:E3:4A:47:1C:E4 (unknown) 


Example of *dfu.py* Output
------------------------

    ~/src/ota-dfu/ $ sudo ./dfu.py -z application_debug_1435008894.zip -a EF:FF:D2:92:9C:2A
    DFU Server start
    unzip_dir: /tmp/application_debug_1435008894_nzjesh
    input_setup
    bin array size:  72352
    scan_and_connect
    dfu_send_image
    [0, 0, 0, 0, 0, 0, 0, 0, 160, 26, 1, 0]
    Sending hex file size
    oper: RESPONSE, proc: START, status: SUCCESS
    dfu_send_info
    PKT_RCPT:      200
    PKT_RCPT:      400
    PKT_RCPT:      600
    PKT_RCPT:      800
    PKT_RCPT:     1000
    PKT_RCPT:     1200
    PKT_RCPT:     1400
    PKT_RCPT:     1600
    PKT_RCPT:     1800
    PKT_RCPT:     2000
    PKT_RCPT:     2200
    PKT_RCPT:     2400
    PKT_RCPT:     2600
    PKT_RCPT:     2800
    PKT_RCPT:     3000
      ...
      ...
      ...
    PKT_RCPT:    69800
    PKT_RCPT:    70000
    PKT_RCPT:    70200
    PKT_RCPT:    70400
    PKT_RCPT:    70600
    PKT_RCPT:    70800
    PKT_RCPT:    71000
    PKT_RCPT:    71200
    PKT_RCPT:    71400
    PKT_RCPT:    71600
    PKT_RCPT:    71800
    PKT_RCPT:    72000
    PKT_RCPT:    72200
    State timeout
    DFU Server done

**NOTE:**  
The final "State timeout" is due to the target peripheral rebooting, as expected, and the disconnect not getting back soon enough.  
This is benign: the update should have been successful and the peripheral should have restarted and run the new firmware. 

**LINKS**  
https://infocenter.nordicsemi.com/index.jsp?topic=%2Fcom.nordic.infocenter.sdk52.v0.9.2%2Fbledfu_application.html&cp=6_0_2_4_2_2


**TODO**  
- Go in DFU Mode buttonless
Check getHandle branch. It works but I just need to manage when the nrf52 is in buttonless mode or not check the DFU version reading the characteristic UUID: 00001534....
- Send encrypted applications
