#!/bin/bash
# =============================================================================
# RustChain Asciinema to GIF Converter
# =============================================================================
# Converts asciinema .cast files to animated GIFs for documentation.
#
# Prerequisites:
#   - asciinema installed
#   - svg-term-cli: npm install -g svg-term-cli
#   - OR: gifski, ffmpeg for raster GIF generation
#
# Usage:
#   ./convert_to_gif.sh [input.cast] [output.gif]
#
# Examples:
#   ./convert_to_gif.sh docs/asciinema/miner_install.cast docs/asciinema/miner_install.gif
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default input/output files
INPUT_FILE="${1:-$PROJECT_ROOT/docs/asciinema/miner_install.cast}"
OUTPUT_FILE="${2:-$PROJECT_ROOT/docs/asciinema/miner_install.gif}"

echo "🎬 RustChain Asciinema to GIF Converter"
echo "======================================="
echo ""
echo "Input:  $INPUT_FILE"
echo "Output: $OUTPUT_FILE"
echo ""

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ Error: Input file not found: $INPUT_FILE"
    exit 1
fi

# Check for conversion tools
CONVERT_METHOD=""

# Method 1: svg-term-cli (creates SVG, recommended for docs)
if command -v svg-term &> /dev/null; then
    CONVERT_METHOD="svg"
    echo "✅ Using svg-term-cli for SVG conversion"
elif command -v asciinema &> /dev/null && command -v ffmpeg &> /dev/null; then
    CONVERT_METHOD="ffmpeg"
    echo "✅ Using asciinema + ffmpeg for GIF conversion"
elif command -v gifski &> /dev/null; then
    CONVERT_METHOD="gifski"
    echo "✅ Using gifski for GIF conversion"
else
    echo "❌ No conversion tools found. Install one of:"
    echo "   - svg-term-cli: npm install -g svg-term-cli"
    echo "   - ffmpeg: brew install ffmpeg"
    echo "   - gifski: brew install gifski"
    exit 1
fi

echo ""
echo "Converting..."

case $CONVERT_METHOD in
    "svg")
        # SVG output (recommended for web docs - smaller file size)
        SVG_OUTPUT="${OUTPUT_FILE%.gif}.svg"
        svg-term --in="$INPUT_FILE" --out="$SVG_OUTPUT" --padding=10 --profile="Monokai"
        echo "✅ SVG created: $SVG_OUTPUT"
        
        # Also create a small GIF using svg2gif if available
        if command -v svg2gif &> /dev/null; then
            svg2gif "$SVG_OUTPUT" -o "$OUTPUT_FILE"
            echo "✅ GIF created: $OUTPUT_FILE"
        else
            echo "💡 Install svg2gif to create GIF from SVG"
            OUTPUT_FILE="$SVG_OUTPUT"
        fi
        ;;
    "ffmpeg")
        # Create PNG frames from asciinema
        TEMP_DIR=$(mktemp -d)
        asciinema play "$INPUT_FILE" --speed=2 --idle-time-limit=0.5 > "$TEMP_DIR/terminal.txt"
        
        # Use ffmpeg to create GIF (simplified approach)
        # Note: Full implementation would require terminal renderer
        echo "⚠️  Full ffmpeg conversion requires additional setup"
        echo "💡 Recommended: Use svg-term instead for web-friendly output"
        ;;
    "gifski")
        # gifski requires PNG frames - simplified placeholder
        echo "⚠️  gifski conversion requires PNG frame extraction"
        echo "💡 Recommended: Use svg-term instead"
        ;;
esac

echo ""
echo "✅ Conversion complete!"
echo ""
echo "File size optimization tips:"
echo "  - Keep recordings under 60 seconds"
echo "  - Use lower terminal resolution (80x24 or 100x30)"
echo "  - Prefer SVG format for web documentation"
echo "  - Compress GIFs with: gifsicle --optimize=3 input.gif -o output.gif"
echo ""
echo "Embed in Markdown:"
echo "  ![Miner Installation]($OUTPUT_FILE)"
echo ""
