Python nRF51 DFU Server
============================

This is my fork of astronomer80's fork of foldedtoad's Python OTA DFU utility. I've modified it to fit my application

============================

A python script for bluez gatttool using pexpect to achive Device Firmware Updates (DFU) to the nRF51.  
The host system is assumed to be some flavor of Linux.

**NOTE:**   
This is probably not a beginner's project.  
Peripheral firmware updating is a complex process, requiring several critical development support steps, not covered here, before the *dfu.py* utility can be used.

It is assumed that your peripheral firmware has been build to Nordic's SDK11 + SoftDevice 2.0.1  
The target peripheral firmware should also include some variation of Nordic's DFU support.

The application is able to detect if the device is running in DFU mode already, and it also has the capability to switch the target to DFU mode, if it supports it. For more information on DFU please see the links at the end of this readme.

This project assumes you are developing on a Linux/Unix or OSX system and deploying to a Linux system. 

Prerequisite
------------

    sudo pip install pexpect
    sudo pip install intelhex

Firmware Build Requirement
--------------------------
* Your nRF51 firmware build method will produce either a firmware hex or bin file named *application.hex* or *application.bin*.  This naming convention is per Nordics DFU specification, which is use by this DFU server as well as the Android Master Control Panel DFU, and iOS DFU app.  
* Your nRF51 firmware build method will produce an Init file (aka *application.dat*).  Again, this is per Nordic's naming conventions. 

Generating `.dat` (init) files
---------------------
Use the `gen_dat` application (you need to compile it with `gcc gen_dat.c -o gen_dat` on first run) to generate a `.dat` file from your `.bin` file. Example:

    ./gen_dat application.bin application.dat
    
Note: The `gen_dat` utility expects a `.bin` file input, so you'll get CRC errors during DFU using a `.dat` file generated from a `.hex` file.

An alternative is to use `nrfutil` from Nordic Semi, but I've found this method to be easier. You may need to edit the `gen_dat` source to fit your specific application.

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
    CD:E3:4A:47:1C:E4 <TARGET_NAME>  
    CD:E3:4A:47:1C:E4 (unknown) 


Example of *dfu.py* Output
------------------------
                                                                                                              
        ================================                                                                      
        ==                            ==                                                                      
        ==         DFU Server         ==                                                                      
        ==                            ==                                                                      
        ================================                                                                      
                                                                                                              
    Sending file application.bin to D3:14:97:B5:C8:FE                                                 
    bin array size:  64608                                                                                    
    Checking DFU State...                                                                                     
    Board needs to switch in DFU mode                                                                         
    Switching to DFU mode                                                                                     
    Enable Notifications in DFU mode                                                                          
    Sending hex file size                                                                                     
    Waiting for Image Size notification                                                                       
    Waiting for INIT DFU notification                                                                         
    Begin DFU                                                                                                 
    Progress: |xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx| 100.0% Complete (64600 of 64608 bytes)     
    Upload complete in 0 minutes and 15 seconds                                                               
    Waiting for DFU complete notification                                                                     
    Waiting for Firmware Validation notification                                                              
    Activate and reset                                                                                        
    DFU Server done  

**NOTE:**  
64600 of 64608 bytes happens because the progress update depends on the packet receipt notification and it's not set to notify on every packet atm (to speed up transfer). In reality, all data is sent. I'll probably fix this later on.

**LINKS**  
https://infocenter.nordicsemi.com/index.jsp?topic=%2Fcom.nordic.infocenter.sdk5.v11.0.0%2Fexamples_ble_dfu.html&cp=4_0_1_4_2_3
