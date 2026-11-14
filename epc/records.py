import mmap
from collections.abc import Iterator
from pathlib import Path

from epc.layout import FormatError, unmask


def split_records(data: bytes, width: int) -> Iterator[tuple[int, bytes]]:
    for offset in range(0, len(data), width):
        yield offset, data[offset : offset + width]


def keyed_records(path: Path, width: int, key: bytes, *, masked: bool = False) -> Iterator[tuple[int, bytes]]:
    if not path.is_file():
        return
    size = path.stat().st_size
    if not size:
        return
    if size % width:
        raise FormatError(f"Invalid native record size: {path.name}")
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        count = size // width

        def key_at(index: int) -> bytes:
            raw = data[index * width : index * width + len(key)]
            return unmask(raw) if masked else raw

        low, high = 0, count
        while low < high:
            middle = (low + high) // 2
            if key_at(middle) < key:
                low = middle + 1
            else:
                high = middle
        while low < count and key_at(low) == key:
            offset = low * width
            raw = data[offset : offset + width]
            yield offset, unmask(raw) if masked else raw
            low += 1
