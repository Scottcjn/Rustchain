import importlib.util
import struct
import zlib
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "extension" / "icons" / "generate_icons.py"


def load_icon_module():
    spec = importlib.util.spec_from_file_location("extension_icon_generator", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_chunks(data):
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    chunks = []
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", data[offset + 8 + length:offset + 12 + length])[0]
        assert crc == zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        chunks.append((chunk_type, payload))
        offset += 12 + length
    return chunks


def test_create_png_writes_valid_png_chunks_and_dimensions():
    icons = load_icon_module()

    data = icons.create_png(16)
    chunks = png_chunks(data)
    ihdr = chunks[0][1]

    assert [chunk_type for chunk_type, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
    assert struct.unpack(">II", ihdr[:8]) == (16, 16)
    assert ihdr[8:] == b"\x08\x06\x00\x00\x00"


def test_pixels_to_png_round_trips_rgba_rows():
    icons = load_icon_module()
    pixels = [
        [255, 0, 0, 255, 0, 255, 0, 255],
        [0, 0, 255, 255, 0, 0, 0, 0],
    ]

    data = icons.pixels_to_png(pixels, 2, 2)
    chunks = dict(png_chunks(data))
    raw = zlib.decompress(chunks[b"IDAT"])

    assert raw == (
        b"\x00" + bytes(pixels[0]) +
        b"\x00" + bytes(pixels[1])
    )


def test_save_icon_writes_requested_size(tmp_path):
    icons = load_icon_module()
    output = tmp_path / "icon.png"

    icons.save_icon(output, 8)

    chunks = png_chunks(output.read_bytes())
    assert struct.unpack(">II", chunks[0][1][:8]) == (8, 8)
