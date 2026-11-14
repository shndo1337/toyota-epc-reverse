import csv
import struct
from pathlib import Path

from epc.layout import unmask

TEST_VIN = "JTDABCDE" + "00" + "0000001"
TEST_FRAME = "ABC10-0000001"

CATALOG = (
    b"010" + b"TEST CAR".ljust(20) + b"101510" + b"ABC10".ljust(50) + b"200502201405A2201405 0".ljust(32)
)
OIL_FILTER = b"90915 0001909150YZZE  01200502200812"
BRAKE_PAD = b"04465 0001044650H020  02200812999999"
VARIANT = (
    b"101510"
    + b"JTDABCDE".ljust(9)
    + b"ABC10L-TEST".ljust(20)
    + b"200502999999"
    + b"ABC10".ljust(7)
    + b"0001"
    + b"003"
    + b"1TEST".ljust(10)
    + b" " * 10
    + b"3D".ljust(5)
    + b"G".ljust(5)
    + b"MTM".ljust(5)
    + b" " * 90
)
VEHICLE = (
    b"0000"
    + struct.pack("<H", 1)
    + b" L  "
    + b"TEST".ljust(13)
    + struct.pack("<HB", 2008, 12)
    + b"040"
    + b"FA10"
    + b"0001"
    + b"Z001"
    + b"0"
)
FRAME_RANGE = (
    b"00080010"
    + b"ABC10".ljust(7)
    + b"-0000001"
    + b" " * 5
    + b"ABC10".ljust(7)
    + b"-0000099"
    + b" " * 5
    + b"TEST".ljust(20)
)
ACCESSORY = [
    "0001",
    "1",
    "DOC",
    "Test accessory",
    "200502",
    "",
    "FLOOR MAT",
    "PZ310-42032-C0",
    "ALL",
    "1",
    "BLACK",
    "ABC10L-TEST",
    "",
]


def part_records() -> list[bytes]:
    oil_header = bytearray(OIL_FILTER + b"1".ljust(86))
    oil_header[41:47] = b"000001"
    oil_header[51:55] = b"0008"
    return [
        BRAKE_PAD + b"1".ljust(86),
        BRAKE_PAD + b"2101" + b"ABC10..GRADE-A".ljust(82),
        BRAKE_PAD + b"2201" + b"MARK TEST".ljust(82),
        bytes(oil_header),
        OIL_FILTER + b"2101" + b"ABC10".ljust(82),
    ]


def write_epc_root(root: Path) -> None:
    region = root / "EU"
    catalog = region / "101510"
    catalog.mkdir(parents=True)
    (region / "SHAMEI.ACD").write_bytes(unmask(CATALOG))
    (region / "HINMEI01.DAT").write_bytes(
        b"90915 " + b"FILTER, OIL".ljust(60) + b"04465 " + b"PAD KIT, DISC BRAKE, FRONT".ljust(60)
    )
    (region / "FIGMEI01.DAT").write_bytes(
        b"1502" + b"OIL FILTER".ljust(120) + b"4705" + b"FRONT DISC BRAKE".ljust(120)
    )
    (region / "JOHOJP.ACD").write_bytes(unmask(VARIANT))
    (catalog / "HNB10151.ACD").write_bytes(unmask(b"".join(part_records())))
    (catalog / "FGI10151.DAT").write_bytes(b"909150YZZE  90915 1502" + b"044650H020  04465 4705")
    (catalog / "KPT10151.DAT").write_bytes(b"000001001")
    (catalog / "KIG10151.D01").write_bytes(b"011TEST".ljust(82))
    (catalog / "KRK10151.DAT").write_bytes(FRAME_RANGE)
    (region / "SIYOPT").mkdir()
    (region / "SIYOPT" / "0001.DAT").write_bytes(b"0001Z001A2AB")

    (root / "FL" / "DM").mkdir(parents=True)
    frame = root / "FL" / "OV" / "ABC10"
    frame.mkdir(parents=True)
    (frame / "0000.ACD").write_bytes(unmask(VEHICLE))

    accessories = root / "JPIO" / "M1"
    accessories.mkdir(parents=True)
    with (accessories / "test.csv").open("w", newline="") as stream:
        csv.writer(stream).writerow(ACCESSORY)
