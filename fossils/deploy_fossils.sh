#!/bin/bash
#
# Deploy The Fossil Record to rustchain.org/fossils
#
# Usage: ./deploy_fossils.sh [destination]
# Example: ./deploy_fossils.sh /var/www/rustchain.org/fossils
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOSSILS_DIR="$SCRIPT_DIR/fossils"
DEFAULT_DEST="/var/www/rustchain.org/fossils"
DEST="${1:-$DEFAULT_DEST}"

echo "🦕 The Fossil Record — Deployment Script"
echo "========================================"
echo ""

# Check source files exist
if [ ! -f "$FOSSILS_DIR/index.html" ]; then
    echo "❌ Error: fossils/index.html not found"
    exit 1
fi

if [ ! -f "$FOSSILS_DIR/fossil_record_export.py" ]; then
    echo "❌ Error: fossils/fossil_record_export.py not found"
    exit 1
fi

if [ ! -f "$FOSSILS_DIR/README.md" ]; then
    echo "❌ Error: fossils/README.md not found"
    exit 1
fi

echo "✅ Source files verified"
echo ""

# Create destination directory
echo "📁 Creating destination: $DEST"
sudo mkdir -p "$DEST"

# Copy files
echo "📦 Copying files..."
sudo cp "$FOSSILS_DIR/index.html" "$DEST/"
sudo cp "$FOSSILS_DIR/fossil_record_export.py" "$DEST/"
sudo cp "$FOSSILS_DIR/README.md" "$DEST/"

# Set permissions
echo "🔐 Setting permissions..."
sudo chown -R www-data:www-data "$DEST" 2>/dev/null || true
sudo chmod 644 "$DEST/index.html"
sudo chmod 755 "$DEST/fossil_record_export.py"
sudo chmod 644 "$DEST/README.md"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📍 Files deployed to: $DEST"
echo ""
echo "🌐 Access the visualizer at:"
echo "   https://rustchain.org/fossils/index.html"
echo ""
echo "🔧 To start the data export service:"
echo "   cd $DEST"
echo "   python3 fossil_record_export.py --serve --port 8080"
echo ""
echo "📖 Documentation: $DEST/README.md"
echo ""

# Optional: Set up systemd service
if [ "$2" != "--no-service" ]; then
    read -p "Set up systemd service? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔧 Creating systemd service..."
        
        SERVICE_FILE="/etc/systemd/system/fossil-record.service"
        sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Fossil Record - Attestation Archaeology API
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$DEST
ExecStart=/usr/bin/python3 $DEST/fossil_record_export.py --serve --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        echo "✅ Service file created: $SERVICE_FILE"
        echo ""
        echo "To enable and start the service:"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable fossil-record"
        echo "  sudo systemctl start fossil-record"
        echo ""
        echo "Check status with:"
        echo "  sudo systemctl status fossil-record"
    fi
fi
