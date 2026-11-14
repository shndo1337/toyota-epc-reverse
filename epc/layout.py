import re
from typing import Final

ENCODING: Final = "cp932"
XOR_MASK: Final = 0xC8
XOR_TABLE: Final = bytes.maketrans(bytes(range(256)), bytes(value ^ XOR_MASK for value in range(256)))
REGIONS: Final = ("EU", "GR", "JP", "US")

_MONTH = re.compile(r"(?:19|20)\d{2}(?:0[1-9]|1[0-2])")
_OPEN_MONTHS: Final = frozenset({"", "999999", "000000"})


class FormatError(ValueError):
    pass


def unmask(data: bytes) -> bytes:
    return data.translate(XOR_TABLE)


def text(raw: bytes) -> str:
    return raw.decode(ENCODING, errors="replace").strip()


def month(raw: bytes) -> str | None:
    value = text(raw)
    if value in _OPEN_MONTHS or not _MONTH.fullmatch(value):
        return None
    return f"{value[:4]}-{value[4:]}"


def catalog_file(prefix: str, extension: str, code: str) -> str:
    return f"{code}/{prefix}{code[:5]}.{extension}"


class Catalogs:
    FILE: Final = "SHAMEI.ACD"
    WIDTH: Final = 111
    NAME: Final = slice(3, 23)
    CODE: Final = slice(23, 29)
    MODEL_CODES: Final = slice(29, 79)
    PRODUCTION_FROM: Final = slice(79, 85)
    PRODUCTION_TO: Final = slice(85, 91)
    REVISION: Final = slice(93, 99)


class PartNames:
    FILE: Final = "HINMEI01.DAT"
    WIDTH: Final = 66
    KEY_WIDTH: Final = 6


class FigureNames:
    FILE: Final = "FIGMEI01.DAT"
    WIDTH: Final = 124
    KEY_WIDTH: Final = 4


class PartRecords:
    PREFIX: Final = "HNB"
    EXTENSION: Final = "ACD"
    WIDTH: Final = 122
    HEADER: Final = b"1"
    CONTINUATION: Final = b"2"
    PNC: Final = slice(0, 6)
    SOURCE_GROUP: Final = slice(6, 10)
    NUMBER: Final = slice(10, 22)
    QUANTITY: Final = slice(22, 24)
    PRODUCTION_FROM: Final = slice(24, 30)
    PRODUCTION_TO: Final = slice(30, 36)
    KIND: Final = slice(36, 37)
    KIND_OFFSET: Final = 36
    APPLICABILITY_GROUP: Final = slice(41, 47)
    FRAME_RANGE_GROUP: Final = slice(51, 55)
    TEXT_KIND: Final = slice(37, 38)
    TEXT_SEQUENCE: Final = slice(38, 40)
    TEXT: Final = slice(40, 122)


class FigureBindings:
    PREFIX: Final = "FGI"
    EXTENSION: Final = "DAT"
    WIDTH: Final = 22
    NUMBER: Final = slice(0, 12)
    PNC: Final = slice(12, 18)
    FIGURE: Final = slice(18, 22)


class Variants:
    OVERSEAS_FILE: Final = "JOHOJP.ACD"
    DOMESTIC_FILE: Final = "JOHOKT.ACD"
    WIDTH: Final = 186
    CATALOG_CODE: Final = slice(0, 6)
    VIN_PREFIX: Final = slice(6, 15)
    MODEL: Final = slice(15, 35)
    PRODUCTION_FROM: Final = slice(35, 41)
    PRODUCTION_TO: Final = slice(41, 47)
    FRAME: Final = slice(47, 54)
    SOURCE_GROUP: Final = slice(54, 58)
    VARIANT_CODE: Final = slice(58, 61)
    ENGINE: Final = slice(61, 81)
    ATTRIBUTES: Final = slice(81, 186)
    ENGINE_CHARACTERISTIC: Final = slice(61, 71)
    SECOND_CHARACTERISTIC: Final = slice(71, 81)
    CHARACTERISTICS_START: Final = 81
    CHARACTERISTIC_WIDTH: Final = 5
    CHARACTERISTIC_COUNT: Final = 21


class ApplicabilityGroups:
    PREFIX: Final = "KPT"
    EXTENSION: Final = "DAT"
    WIDTH: Final = 9
    KEY_WIDTH: Final = 6
    MEMBER: Final = slice(6, 9)


class CharacteristicLegend:
    PREFIX: Final = "KIG"
    EXTENSION: Final = "D01"
    WIDTH: Final = 82
    CATEGORY: Final = slice(0, 2)
    VALUE: Final = slice(2, 12)


class FrameRanges:
    PREFIX: Final = "KRK"
    EXTENSION: Final = "DAT"
    WIDTH: Final = 68
    KEY_WIDTH: Final = 4
    START_FRAME: Final = slice(8, 15)
    START_SERIAL: Final = slice(16, 23)
    END_FRAME: Final = slice(28, 35)
    END_SERIAL: Final = slice(36, 43)


class VehicleBlocks:
    FOLDER: Final = "FL"
    DOMESTIC: Final = "DM"
    OVERSEAS: Final = "OV"
    EXTENSION: Final = ".ACD"
    WIDTH: Final = 42
    SERIAL_PREFIX: Final = slice(0, 4)
    SERIAL_SUFFIX_OFFSET: Final = 4
    MODEL_SUFFIX: Final = slice(6, 10)
    MODEL_TAIL: Final = slice(10, 23)
    YEAR_OFFSET: Final = 23
    MONTH_OFFSET: Final = 25
    COLOR: Final = slice(26, 29)
    TRIM: Final = slice(29, 33)
    SPECIFICATION_GROUP: Final = slice(33, 37)
    SPECIFICATION_CODE: Final = slice(37, 41)


class Specifications:
    FOLDER: Final = "SIYOPT"
    WIDTH: Final = 12
    CATEGORY: Final = slice(8, 10)
    VALUE: Final = slice(10, 12)


class Prices:
    FILE: Final = "JP/KAKAKU.DAT"
    WIDTH: Final = 20
    KEY_WIDTH: Final = 12
    AMOUNT: Final = slice(12, 20)
    CURRENCY: Final = "JPY"


class RelatedNumbers:
    KEY_WIDTH: Final = 12
    SOURCES: Final = (("DAIHIN.DAT", 41, slice(17, 29)), ("CHOHIN.DAT", 43, slice(15, 27)))


class ImageIndex:
    WIDTH: Final = 15
    KEY_WIDTH: Final = 7
    POINTER_OFFSET: Final = 7
    POINTER: Final = "<II"


class Thumbnails:
    PREFIX: Final = "EMK"
    INDEX_EXTENSION: Final = "IA0"
    DATA_EXTENSION: Final = "DAT"
    SIGNATURE: Final = b"\x89PNG"


class FigureImages:
    PREFIX: Final = "BZI"
    EXTENSION: Final = "DAT"
    WIDTH: Final = 37
    SEQUENCE: Final = slice(4, 8)
    IMAGE: Final = slice(8, 15)
    PRODUCTION_FROM: Final = slice(15, 21)
    PRODUCTION_TO: Final = slice(21, 27)


class Diagrams:
    INDEX_PATTERN: Final = "*/IMAGEF.IA0"
    DATA_EXTENSION: Final = ".DAT"
    MAX_BLOCK_SIZE: Final = 16 * 1024 * 1024
    MAX_PIXELS: Final = 30_000_000
    HEADER_SIZE: Final = 21
    VERSION: Final = slice(3, 4)
    SUPPORTED_VERSIONS: Final = (b"3", b"4")
    WIDTH: Final = slice(11, 13)
    HEIGHT: Final = slice(13, 15)
    COMPRESSION: Final = slice(15, 16)
    GROUP4: Final = b"3"
    LENGTH: Final = slice(16, 19)
