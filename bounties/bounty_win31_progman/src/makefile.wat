# Open Watcom makefile for Windows 3.1 Validator
#
# Usage: wmake -f makefile.wat

CC = wcl
CFLAGS = -bt=windows -c -dWIN16 -ms
LINKFLAGS = bt=windows file win31_validator

all: RustVal.exe

RustVal.exe: win31_validator.obj
    $(CC) -bt=windows -fe=RustVal.exe win31_validator.obj

win31_validator.obj: win31_validator.c win31_validator.h
    $(CC) $(CFLAGS) win31_validator.c

clean:
    del *.obj
    del *.map
    del RustVal.exe
