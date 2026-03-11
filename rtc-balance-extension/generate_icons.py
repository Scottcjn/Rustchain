#!/usr/bin/env python3
"""Generate placeholder icons for the RTC Balance Viewer extension."""

import base64
import os

# Simple PNG icon generator (16x16, 48x48, 128x128)
# Creates a gradient purple/blue icon with "RTC" text placeholder

def create_minimal_png(size):
    """Create a minimal valid PNG file with a solid color."""
    # This creates a simple PNG with gradient-like appearance
    # Using a base64 encoded minimal PNG for simplicity
    
    # For a proper implementation, you'd use PIL/Pillow
    # This is a placeholder that creates valid PNG files
    
    width = height = size
    
    # PNG signature
    png_signature = b'\x89PNG\r\n\x1a\n'
    
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib_crc32(chunk)
        return len(data).to_bytes(4, 'big') + chunk + crc.to_bytes(4, 'big')
    
    def zlib_crc32(data):
        import zlib
        return zlib.crc32(data) & 0xffffffff
    
    # IHDR chunk
    ihdr_data = (
        width.to_bytes(4, 'big') +
        height.to_bytes(4, 'big') +
        b'\x08\x06\x00\x00\x00'  # 8-bit RGBA, no interlace
    )
    ihdr = make_chunk(b'IHDR', ihdr_data)
    
    # Create pixel data (gradient purple to blue)
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # Filter byte (none)
        for x in range(width):
            # Gradient from purple (#667eea) to blue (#764ba2)
            ratio = x / width
            r = int(102 + (118 - 102) * ratio)
            g = int(126 + (75 - 126) * ratio)
            b = int(234 + (162 - 234) * ratio)
            a = 255
            raw_data += bytes([r, g, b, a])
    
    # Compress pixel data
    import zlib
    compressed = zlib.compress(raw_data, 9)
    idat = make_chunk(b'IDAT', compressed)
    
    # IEND chunk
    iend = make_chunk(b'IEND', b'')
    
    return png_signature + ihdr + idat + iend


def main():
    icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
    os.makedirs(icons_dir, exist_ok=True)
    
    sizes = [16, 48, 128]
    
    for size in sizes:
        png_data = create_minimal_png(size)
        filename = os.path.join(icons_dir, f'icon{size}.png')
        with open(filename, 'wb') as f:
            f.write(png_data)
        print(f"Created {filename}")
    
    print("Icons generated successfully!")


if __name__ == '__main__':
    main()
