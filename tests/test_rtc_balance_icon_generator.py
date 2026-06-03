import importlib.util
import struct
import zlib
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "rtc-balance-extension" / "generate_icons.py"


def load_icon_module():
    spec = importlib.util.spec_from_file_location("rtc_balance_icon_generator", MODULE_PATH)
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


def test_create_minimal_png_has_valid_chunks_and_dimensions():
    icons = load_icon_module()

    data = icons.create_minimal_png(16)
    chunks = png_chunks(data)

    assert [chunk_type for chunk_type, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
    assert struct.unpack(">II", chunks[0][1][:8]) == (16, 16)
    assert chunks[0][1][8:] == b"\x08\x06\x00\x00\x00"


def test_create_minimal_png_encodes_one_filter_byte_per_row():
    icons = load_icon_module()

    data = icons.create_minimal_png(4)
    chunks = dict(png_chunks(data))
    raw = zlib.decompress(chunks[b"IDAT"])
    row_size = 1 + 4 * 4

    assert len(raw) == 4 * row_size
    assert raw[0::row_size] == b"\x00" * 4


def test_main_writes_expected_icon_sizes(tmp_path, monkeypatch):
    icons = load_icon_module()
    fake_script = tmp_path / "generate_icons.py"
    fake_script.write_text("# test shim\n")
    monkeypatch.setattr(icons, "__file__", str(fake_script))

    icons.main()

    for size in [16, 48, 128]:
        path = tmp_path / "icons" / f"icon{size}.png"
        chunks = png_chunks(path.read_bytes())
        assert struct.unpack(">II", chunks[0][1][:8]) == (size, size)
