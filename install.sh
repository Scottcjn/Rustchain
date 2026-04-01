echo ""
echo -e "${GREEN}[4/6]${NC} Downloading and verifying miner..."

mkdir -p "$INSTALL_DIR"

# Download miner script with integrity verification
if command -v curl &>/dev/null; then
    curl -fsSL "$MINER_URL" -o "$INSTALL_DIR/rustchain_miner.py" 2>/dev/null
    curl -fsSL "$FINGERPRINT_URL" -o "$INSTALL_DIR/fingerprint_checks.py" 2>/dev/null
    # Verify integrity using SHA256 checksum
    EXPECTED_CHECKSUM="$(curl -fsSL "$MINER_URL.sha256" 2>/dev/null)"
    ACTUAL_CHECKSUM="$(sha256sum "$INSTALL_DIR/rustchain_miner.py" | cut -d' ' -f1)"
    if [ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ]; then
        echo -e "${RED}  Downloaded script's integrity could not be verified.${NC}"
        exit 1
    fi
elif command -v wget &>/dev/null; then
    wget -q "$MINER_URL" -O "$INSTALL_DIR/rustchain_miner.py" 2>/dev/null
    wget -q "$FINGERPRINT_URL" -O "$INSTALL_DIR/fingerprint_checks.py" 2>/dev/null
    # Verify integrity using SHA256 checksum
    EXPECTED_CHECKSUM="$(wget -q -O- "$MINER_URL.sha256" 2>/dev/null)"
    ACTUAL_CHECKSUM="$(sha256sum "$INSTALL_DIR/rustchain_miner.py" | cut -d' ' -f1)"
    if [ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ]; then
        echo -e "${RED}  Downloaded script's integrity could not be verified.${NC}"
        exit 1
    fi
else
    echo -e "${RED}  Neither curl nor wget found. Cannot download.${NC}"
    exit 1
fi

if [ ! -s "$INSTALL_DIR/rustchain_miner.py" ]; then
    echo -e "${RED}  Download failed. Check your internet connection.${NC}"
    exit 1
fi

echo "  Downloaded and verified to: $INSTALL_DIR/"