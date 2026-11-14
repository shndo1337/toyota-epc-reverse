from pathlib import Path

import pytest

from epc.layout import (
    Catalogs,
    FormatError,
    FrameRanges,
    PartRecords,
    Variants,
    VehicleBlocks,
    month,
    text,
    unmask,
)
from epc.records import keyed_records, split_records
from tests.samples import CATALOG, FRAME_RANGE, VARIANT, VEHICLE, part_records


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"200502", "2005-02"),
        (b"199912", "1999-12"),
        (b"999999", None),
        (b"000000", None),
        (b"      ", None),
        (b"202313", None),
        (b"202300", None),
        (b"hello!", None),
    ],
)
def test_month(raw: bytes, expected: str | None) -> None:
    assert month(raw) == expected


def test_sample_records_match_the_layout() -> None:
    assert len(CATALOG) == Catalogs.WIDTH
    assert len(VARIANT) == Variants.WIDTH
    assert len(VEHICLE) == VehicleBlocks.WIDTH
    assert len(FRAME_RANGE) == FrameRanges.WIDTH
    assert {len(row) for row in part_records()} == {PartRecords.WIDTH}


def test_text_keeps_invalid_cp932_readable() -> None:
    assert text(b" OIL \x81") == "OIL �"


def test_unmask_is_an_involution() -> None:
    data = bytes(range(256))
    assert unmask(unmask(data)) == data
    assert unmask(b"\x00") == b"\xc8"


def test_split_records() -> None:
    assert list(split_records(b"aabbcc", 2)) == [(0, b"aa"), (2, b"bb"), (4, b"cc")]


def test_keyed_records_finds_every_row_with_the_key(tmp_path: Path) -> None:
    path = tmp_path / "sorted.dat"
    path.write_bytes(b"A1B1B2B3C1")
    assert list(keyed_records(path, 2, b"B")) == [(2, b"B1"), (4, b"B2"), (6, b"B3")]
    assert list(keyed_records(path, 2, b"D")) == []


def test_keyed_records_reads_masked_files(tmp_path: Path) -> None:
    path = tmp_path / "masked.dat"
    path.write_bytes(unmask(b"A1B2"))
    assert list(keyed_records(path, 2, b"B", masked=True)) == [(2, b"B2")]


def test_keyed_records_tolerates_missing_and_empty_files(tmp_path: Path) -> None:
    empty = tmp_path / "empty.dat"
    empty.write_bytes(b"")
    assert list(keyed_records(tmp_path / "absent.dat", 2, b"A")) == []
    assert list(keyed_records(empty, 2, b"A")) == []


def test_keyed_records_rejects_a_partial_record(tmp_path: Path) -> None:
    path = tmp_path / "broken.dat"
    path.write_bytes(b"A1B")
    with pytest.raises(FormatError, match="record size"):
        list(keyed_records(path, 2, b"A"))
