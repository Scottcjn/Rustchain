# Open Watcom makefile for MS-DOS Validator
# Creates .COM executable for real mode DOS
#
# Usage: wmake -f makefile.wat

CC = wcl
CFLAGS = -bt=dos -c -ms -dDOS
LINKFLAGS = bt=dos file dos_validator

all: rustdos.com

rustdos.com: dos_validator.obj
    $(CC) -bt=dos -fe=rustdos.com dos_validator.obj

dos_validator.obj: dos_validator.c dos_validator.h
    $(CC) $(CFLAGS) dos_validator.c

clean:
    del *.obj
    del *.map
    del rustdos.com
