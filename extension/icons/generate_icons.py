#!/usr/bin/env python3
"""Generate PNG icons from SVG for RustChain Wallet extension."""

import base64
import struct
import zlib
import os

def create_png(size=128, color_primary=(0, 212, 255), color_secondary=(0, 255, 136)):
    """Create a simple PNG icon programmatically."""
    w = h = size
    center = size // 2
    radius = size // 2 - 2

    # Create RGBA image data
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            # Calculate distance from center
            dx = x - center
            dy = y - center
            dist = (dx * dx + dy * dy) ** 0.5

            if dist > radius:
                # Transparent background
                row.extend([0, 0, 0, 0])
            else:
                # Dark blue background
                bg = (26, 26, 46, 255)

                # Draw outer ring
                ring_inner = radius - 4
                ring_outer = radius
                if ring_inner < dist <= ring_outer:
                    row.extend([*color_primary, 255])
                # Draw inner circle
                elif dist <= radius - 8:
                    inner_color = (22, 33, 62, 255)
                    row.extend([*inner_color, 255])
                else:
                    row.extend([*bg, 255])
        pixels.append(row)

    # Add checkmark
    check_points = [
        (center - size//6, center),
        (center - size//12, center + size//8),
        (center + size//4, center - size//6),
    ]

    # Simple line drawing for checkmark
    for i in range(len(check_points) - 1):
        x0, y0 = check_points[i]
        x1, y1 = check_points[i + 1]
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for s in range(steps + 1):
            t = s / steps if steps > 0 else 0
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            if 0 <= y < h and 0 <= x < w:
                idx = y * w * 4 + x * 4
                pixels[y][x * 4:x * 4 + 4] = [*color_secondary, 255]

    # Convert to PNG
    return pixels_to_png(pixels, w, h)


def pixels_to_png(pixels, w, h):
    """Convert pixel array to PNG binary."""
    def png_chunk(chunk_type, data):
        chunk_len = struct.pack('>I', len(data))
        chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
        return chunk_len + chunk_type + data + chunk_crc

    # PNG signature
    signature = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)

    # IDAT chunk (image data)
    raw_data = b''
    for row in pixels:
        raw_data += b'\x00' + bytes(row)

    compressed = zlib.compress(raw_data, 9)
    idat = png_chunk(b'IDAT', compressed)

    # IEND chunk
    iend = png_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend


def save_icon(path, size):
    """Save PNG icon to file."""
    png_data = create_png(size)
    with open(path, 'wb') as f:
        f.write(png_data)
    print(f"Generated {path} ({size}x{size})")


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    save_icon(os.path.join(script_dir, 'icon16.png'), 16)
    save_icon(os.path.join(script_dir, 'icon48.png'), 48)
    save_icon(os.path.join(script_dir, 'icon128.png'), 128)
    print("All icons generated successfully!")
