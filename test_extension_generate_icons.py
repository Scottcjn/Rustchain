# SPDX-License-Identifier: MIT

import importlib.util
import struct
import zlib
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "extension" / "icons" / "generate_icons.py"
SPEC = importlib.util.spec_from_file_location("generate_icons", MODULE_PATH)
generate_icons = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_icons)


def _png_chunks(data):
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        yield chunk_type, chunk_data
        offset += 12 + length


def _decompressed_rows(png_data):
    idat = b"".join(data for chunk_type, data in _png_chunks(png_data) if chunk_type == b"IDAT")
    return zlib.decompress(idat)


def test_pixels_to_png_builds_valid_rgba_png():
    pixels = [
        [255, 0, 0, 255, 0, 255, 0, 255],
        [0, 0, 255, 255, 255, 255, 255, 0],
    ]

    png_data = generate_icons.pixels_to_png(pixels, 2, 2)
    chunks = list(_png_chunks(png_data))

    assert png_data.startswith(b"\x89PNG\r\n\x1a\n")
    assert chunks[0][0] == b"IHDR"
    assert struct.unpack(">II", chunks[0][1][:8]) == (2, 2)
    assert chunks[-1] == (b"IEND", b"")
    assert _decompressed_rows(png_data) == (
        b"\x00\xff\x00\x00\xff\x00\xff\x00\xff"
        b"\x00\x00\x00\xff\xff\xff\xff\xff\x00"
    )


def test_create_png_uses_requested_dimensions_and_transparency():
    png_data = generate_icons.create_png(size=16)
    ihdr = next(data for chunk_type, data in _png_chunks(png_data) if chunk_type == b"IHDR")
    rows = _decompressed_rows(png_data)

    assert struct.unpack(">II", ihdr[:8]) == (16, 16)
    assert ihdr[8:13] == bytes([8, 6, 0, 0, 0])
    assert rows[0] == 0
    assert rows[1:5] == b"\x00\x00\x00\x00"


def test_save_icon_writes_png_file(tmp_path, capsys):
    target = tmp_path / "icon16.png"

    generate_icons.save_icon(target, 16)

    assert target.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "Generated" in capsys.readouterr().out
