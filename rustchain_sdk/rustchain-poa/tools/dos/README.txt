RustChain DOS Tools - PoA Validator TCP Sender
-------------------------------------------------

This directory contains a C program for DOS that uses WATTCP to send a simple JSON fingerprint to the RustChain PoA REST API.

Files:
- poa_dos.c : C source file using WATTCP sockets
- Compile with: Watcom C, DJGPP, or Borland C with WATTCP installed
- Requires: Wattcp.cfg configured to use your IP gateway/DNS/etc

Run inside DOSBox with NE2000 enabled, or real DOS with packet driver.

Example:
    POSTs the following to http://192.168.1.100:5000/validate
    {
        "device":"DOSBox",
        "cpu":"386DX",
        "bios":"AMI 1994",
        "fingerprint":"DOS-LEGIT-1"
    }

Make sure your RustChain REST API is running before testing.
