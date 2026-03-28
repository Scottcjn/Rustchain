# Makefile for Apple II RustChain Miner
# Requires CC65 toolchain: https://cc65.github.io/
#
# Build:  make
# Clean:  make clean

CC      = cl65
TARGET  = apple2enh
CFLAGS  = -t $(TARGET) -O --static-locals
LDFLAGS = -t $(TARGET)

SOURCES = miner6502.c sha256_6502.c
OBJECTS = $(SOURCES:.c=.o)
BINARY  = MINER.SYSTEM

.PHONY: all clean disk

all: $(BINARY)

$(BINARY): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $(OBJECTS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

# Create a ProDOS disk image (requires AppleCommander or similar)
disk: $(BINARY)
	@echo "To create a bootable disk image:"
	@echo "  ac -pro140 miner.po MINER"
	@echo "  ac -p miner.po MINER.SYSTEM SYS < $(BINARY)"

clean:
	rm -f $(OBJECTS) $(BINARY)
