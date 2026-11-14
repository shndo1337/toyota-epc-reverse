import io
import struct
from pathlib import Path

import pytest
from PIL import Image, TiffImagePlugin

from epc.layout import FormatError
from epc.native import NativeCatalog


def group4_payload(bitmap: Image.Image) -> bytes:
    buffer = io.BytesIO()
    bitmap.save(buffer, format="TIFF", compression="group4")
    with TiffImagePlugin.TiffImageFile(io.BytesIO(buffer.getvalue())) as tiff:
        offset, size = tiff.tag_v2[273][0], tiff.tag_v2[279][0]
    return buffer.getvalue()[offset : offset + size]


def write_diagram(root: Path, image: str, record: bytes) -> None:
    folder = root / "EU" / "A1"
    folder.mkdir()
    (folder / "IMAGEF.IA0").write_bytes(image.encode() + struct.pack("<II", 1, len(record)))
    (folder / "IMAGEF.DAT").write_bytes(record)


def diagram_record(version: bytes, payload: bytes, size: int = 16) -> bytes:
    header = b"\0\0\0" + version + b"123456A" + struct.pack(">HH", size, size)
    return header + b"3" + len(payload).to_bytes(3, "big") + b"\0\0" + payload


@pytest.mark.parametrize("version", [b"3", b"4"])
def test_full_resolution_diagram(epc_root: Path, version: bytes) -> None:
    bitmap = Image.new("1", (16, 16), 1)
    bitmap.putpixel((4, 5), 0)
    write_diagram(epc_root, "123456A", diagram_record(version, group4_payload(bitmap)))

    png = NativeCatalog(epc_root).diagram("EU", "123456A")

    assert png is not None
    with Image.open(io.BytesIO(png)) as result:
        assert result.size == (16, 16)
        assert result.getpixel((4, 5)) != result.getpixel((0, 0))


def test_unsupported_diagram_encoding(epc_root: Path) -> None:
    write_diagram(epc_root, "123456A", diagram_record(b"9", b"payload"))
    with pytest.raises(FormatError, match="Unsupported"):
        NativeCatalog(epc_root).diagram("EU", "123456A")


def test_missing_diagram(epc_root: Path) -> None:
    assert NativeCatalog(epc_root).diagram("EU", "ZZZZZZZ") is None


def test_source_paths_cannot_escape_the_root(epc_root: Path) -> None:
    native = NativeCatalog(epc_root)
    assert native.path("EU/SHAMEI.ACD").is_file()
    with pytest.raises(ValueError, match="outside"):
        native.path("../outside.txt")
