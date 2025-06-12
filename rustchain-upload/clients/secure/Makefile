# RustChain Secure Miners Makefile

# Windows build (requires MinGW)
windows:
	gcc -o rustchain_secure_miner.exe rustchain_secure_miner_windows.c -lws2_32 -mwindows -static
	@echo "Windows executable built: rustchain_secure_miner.exe"

# PowerPC build (requires AltiVec support)
powerpc:
	gcc -o rustchain_secure_miner_ppc rustchain_secure_miner_ppc.c -maltivec -mabi=altivec
	@echo "PowerPC executable built: rustchain_secure_miner_ppc"

# Generic Unix build (without AltiVec)
unix:
	gcc -o rustchain_secure_miner_ppc rustchain_secure_miner_ppc.c
	@echo "Unix executable built (no AltiVec): rustchain_secure_miner_ppc"

clean:
	rm -f rustchain_secure_miner.exe rustchain_secure_miner_ppc

all: windows powerpc