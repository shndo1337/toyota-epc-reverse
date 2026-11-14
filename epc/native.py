import hashlib
import io
import re
import struct
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image

from epc.layout import (
    ENCODING,
    ApplicabilityGroups,
    CharacteristicLegend,
    Diagrams,
    FigureImages,
    FormatError,
    FrameRanges,
    ImageIndex,
    PartRecords,
    Prices,
    RelatedNumbers,
    Specifications,
    Thumbnails,
    Variants,
    VehicleBlocks,
    catalog_file,
    month,
    text,
    unmask,
)
from epc.records import keyed_records

Record = dict[str, Any]
FrameRange = tuple[str, str, str, str]

DATASET_EDITION = "2025.01"
_FRAME = re.compile(r"[A-Z0-9]{3,10}")
_SERIAL = re.compile(r"[A-Z0-9]{4}\d{3}")
_SPECIFICATION_KEY = re.compile(r"[A-Z0-9]{4}")

_TIFF_SHORT = 3
_TIFF_LONG = 4
_TIFF_GROUP4 = 4
_TIFF_HEADER = struct.Struct("<2sHI")
_TIFF_ENTRY = struct.Struct("<HHII")


def _group4_tiff(width: int, height: int, payload: bytes) -> bytes:
    tags = [
        (256, _TIFF_LONG, width),
        (257, _TIFF_LONG, height),
        (258, _TIFF_SHORT, 1),
        (259, _TIFF_SHORT, _TIFF_GROUP4),
        (262, _TIFF_SHORT, 0),
        (266, _TIFF_SHORT, 1),
        (273, _TIFF_LONG, 0),
        (278, _TIFF_LONG, height),
        (279, _TIFF_LONG, len(payload)),
        (293, _TIFF_LONG, 0),
    ]
    data_offset = _TIFF_HEADER.size + 2 + _TIFF_ENTRY.size * len(tags) + 4
    entries = b"".join(
        _TIFF_ENTRY.pack(tag, kind, 1, data_offset if tag == 273 else value) for tag, kind, value in tags
    )
    header = _TIFF_HEADER.pack(b"II", 42, _TIFF_HEADER.size)
    return header + struct.pack("<H", len(tags)) + entries + struct.pack("<I", 0) + payload


class NativeCatalog:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self._applications = lru_cache(maxsize=384)(self._read_applications)
        self._group_members = lru_cache(maxsize=1024)(self._read_group_members)
        self._legend = lru_cache(maxsize=128)(self._read_legend)
        self._characteristics = lru_cache(maxsize=256)(self._read_characteristics)
        self._frame_ranges = lru_cache(maxsize=1024)(self._read_frame_ranges)
        self._thumbnails = lru_cache(maxsize=128)(self._read_thumbnail_index)
        self._image_files = lru_cache(maxsize=4)(self._find_image_files)
        self._diagrams = lru_cache(maxsize=128)(self._render_diagram)

    def clear_caches(self) -> None:
        for cache in (
            self._applications,
            self._group_members,
            self._legend,
            self._characteristics,
            self._frame_ranges,
            self._thumbnails,
            self._image_files,
            self._diagrams,
        ):
            cache.cache_clear()

    def path(self, relative: str) -> Path:
        result = (self.root / relative).resolve()
        if not result.is_relative_to(self.root):
            raise ValueError("Source path outside EPC root")
        return result

    def catalog_path(self, region: str, prefix: str, extension: str, code: str) -> Path:
        return self.root / region / catalog_file(prefix, extension, code)

    def part_records_path(self, region: str, code: str) -> Path:
        return self.catalog_path(region, PartRecords.PREFIX, PartRecords.EXTENSION, code)

    def applications(self, region: str, code: str, pnc: str) -> list[Record]:
        return self._applications(region, code, pnc)

    def group_members(self, region: str, code: str, group: str) -> frozenset[str]:
        return self._group_members(region, code, group)

    def characteristic_legend(self, region: str, code: str) -> dict[str, tuple[str, str]]:
        return self._legend(region, code)

    def variant_characteristics(self, path: str, offset: int) -> dict[str, str]:
        return self._characteristics(path, offset)

    def frame_ranges(self, region: str, code: str, group: str) -> tuple[FrameRange, ...]:
        return self._frame_ranges(region, code, group)

    def diagram(self, region: str, image: str) -> bytes | None:
        return self._diagrams(region, image)

    def read_part_record(self, region: str, code: str, offset: int) -> bytes | None:
        path = self.part_records_path(region, code)
        if offset % PartRecords.WIDTH or offset >= path.stat().st_size:
            return None
        with path.open("rb") as stream:
            stream.seek(offset)
            return unmask(stream.read(PartRecords.WIDTH))

    def vehicle_block(self, domain: str, frame: str, serial: str) -> Record | None:
        if not _FRAME.fullmatch(frame) or not _SERIAL.fullmatch(serial):
            return None
        relative = f"{VehicleBlocks.FOLDER}/{domain}/{frame}/{serial[:4]}{VehicleBlocks.EXTENSION}"
        path = self.root / relative
        if not path.is_file():
            return None
        raw = path.read_bytes()
        data = unmask(raw)
        if len(data) % VehicleBlocks.WIDTH:
            raise FormatError("Invalid vehicle block length")
        prefix, suffix = serial[:4].encode(), int(serial[4:])
        for offset in range(0, len(data), VehicleBlocks.WIDTH):
            row = data[offset : offset + VehicleBlocks.WIDTH]
            if row[VehicleBlocks.SERIAL_PREFIX] != prefix:
                continue
            if struct.unpack_from("<H", row, VehicleBlocks.SERIAL_SUFFIX_OFFSET)[0] != suffix:
                continue
            year = struct.unpack_from("<H", row, VehicleBlocks.YEAR_OFFSET)[0]
            production_month = row[VehicleBlocks.MONTH_OFFSET]
            if not 1900 <= year <= 2099 or not 1 <= production_month <= 12:
                continue
            model = f"{frame}{text(row[VehicleBlocks.MODEL_SUFFIX])}-{text(row[VehicleBlocks.MODEL_TAIL])}"
            return {
                "frame": frame,
                "serial": serial,
                "frame_number": f"{frame}-{serial}",
                "model": model,
                "production_month": f"{year:04d}-{production_month:02d}",
                "color": text(row[VehicleBlocks.COLOR]),
                "trim": text(row[VehicleBlocks.TRIM]),
                "specification_group": text(row[VehicleBlocks.SPECIFICATION_GROUP]),
                "specification_code": text(row[VehicleBlocks.SPECIFICATION_CODE]),
                "source_path": relative,
                "source_offset": offset,
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_hex": row.hex(),
                "record_size": VehicleBlocks.WIDTH,
            }
        return None

    def specifications(self, vehicle: Record, region: str) -> list[Record]:
        group, code = vehicle["specification_group"], vehicle["specification_code"]
        if not _SPECIFICATION_KEY.fullmatch(group) or not _SPECIFICATION_KEY.fullmatch(code):
            return []
        path = self.root / region / Specifications.FOLDER / f"{group}.DAT"
        relative = path.relative_to(self.root).as_posix()
        return [
            {
                "category": text(row[Specifications.CATEGORY]),
                "value": text(row[Specifications.VALUE]),
                "source_offset": offset,
                "source_path": relative,
            }
            for offset, row in keyed_records(path, Specifications.WIDTH, (group + code).encode())
        ]

    def price(self, number: str) -> Record | None:
        key = number.encode().ljust(Prices.KEY_WIDTH)
        found = next(keyed_records(self.root / Prices.FILE, Prices.WIDTH, key), None)
        if found is None:
            return None
        offset, row = found
        raw = text(row[Prices.AMOUNT])
        return {
            "amount": int(raw) if raw.isdigit() else None,
            "currency": Prices.CURRENCY,
            "source_path": Prices.FILE,
            "source_offset": offset,
            "raw_value": raw,
            "dataset": DATASET_EDITION,
        }

    def related_numbers(self, number: str, regions: list[str]) -> list[Record]:
        key = number.encode().ljust(RelatedNumbers.KEY_WIDTH)
        result = []
        for region in regions:
            for filename, width, field in RelatedNumbers.SOURCES:
                for offset, row in keyed_records(self.root / region / filename, width, key):
                    result.append(
                        {
                            "region": region,
                            "number": text(row[field]),
                            "source_type": filename.split(".")[0],
                            "source_path": f"{region}/{filename}",
                            "source_offset": offset,
                            "raw_record": text(row),
                        }
                    )
        return result

    def thumbnail(self, region: str, code: str, image: str) -> bytes | None:
        pointer = self._thumbnails(region, code).get(image)
        if not pointer:
            return None
        offset, size = pointer
        path = self.catalog_path(region, Thumbnails.PREFIX, Thumbnails.DATA_EXTENSION, code)
        with path.open("rb") as stream:
            stream.seek(offset - 1)
            data = stream.read(size)
        return data if data.startswith(Thumbnails.SIGNATURE) else None

    def figure_images(self, region: str, code: str, figure: str) -> list[Record]:
        path = self.catalog_path(region, FigureImages.PREFIX, FigureImages.EXTENSION, code)
        return [
            {
                "image": text(row[FigureImages.IMAGE]),
                "sequence": text(row[FigureImages.SEQUENCE]),
                "production_from": month(row[FigureImages.PRODUCTION_FROM]),
                "production_to": month(row[FigureImages.PRODUCTION_TO]),
                "source_offset": offset,
            }
            for offset, row in keyed_records(path, FigureImages.WIDTH, figure.encode())
        ]

    def _read_applications(self, region: str, code: str, pnc: str) -> list[Record]:
        path = self.part_records_path(region, code)
        source_path = path.relative_to(self.root).as_posix()
        key = pnc.encode(ENCODING).ljust(PartRecords.PNC.stop)
        result: list[Record] = []
        current: Record | None = None
        for offset, row in keyed_records(path, PartRecords.WIDTH, key, masked=True):
            kind = row[PartRecords.KIND]
            if kind == PartRecords.HEADER:
                current = {
                    "id": f"{region}:{code}:{offset}",
                    "catalog_code": f"{region}:{code}",
                    "part_number": text(row[PartRecords.NUMBER]),
                    "pnc": text(row[PartRecords.PNC]),
                    "source_group": text(row[PartRecords.SOURCE_GROUP]),
                    "quantity": text(row[PartRecords.QUANTITY]),
                    "production_from": month(row[PartRecords.PRODUCTION_FROM]),
                    "production_to": month(row[PartRecords.PRODUCTION_TO]),
                    "source_offset": offset,
                    "source_path": source_path,
                    "raw_record": row.decode(ENCODING, errors="replace"),
                    "applicability_group": text(row[PartRecords.APPLICABILITY_GROUP]),
                    "frame_range_group": text(row[PartRecords.FRAME_RANGE_GROUP]),
                    "texts": [],
                }
                result.append(current)
            elif kind == PartRecords.CONTINUATION and current:
                current["texts"].append(
                    {
                        "kind": text(row[PartRecords.TEXT_KIND]),
                        "sequence": text(row[PartRecords.TEXT_SEQUENCE]),
                        "text": text(row[PartRecords.TEXT]),
                        "source_offset": offset,
                    }
                )
        return result

    def _read_group_members(self, region: str, code: str, group: str) -> frozenset[str]:
        layout = ApplicabilityGroups
        path = self.catalog_path(region, layout.PREFIX, layout.EXTENSION, code)
        key = group.encode().ljust(layout.KEY_WIDTH)
        return frozenset(text(row[layout.MEMBER]) for _, row in keyed_records(path, layout.WIDTH, key))

    def _read_legend(self, region: str, code: str) -> dict[str, tuple[str, str]]:
        layout = CharacteristicLegend
        path = self.catalog_path(region, layout.PREFIX, layout.EXTENSION, code)
        if not path.exists():
            return {}
        data = path.read_bytes()
        legend = {}
        for index, offset in enumerate(range(0, len(data), layout.WIDTH), start=1):
            row = data[offset : offset + layout.WIDTH]
            legend[f"{index:03d}"] = (text(row[layout.CATEGORY]), text(row[layout.VALUE]))
        return legend

    def _read_characteristics(self, path: str, offset: int) -> dict[str, str]:
        with self.path(path).open("rb") as stream:
            stream.seek(offset)
            row = unmask(stream.read(Variants.WIDTH))
        result = {
            "01": text(row[Variants.ENGINE_CHARACTERISTIC]),
            "02": text(row[Variants.SECOND_CHARACTERISTIC]),
        }
        for index in range(Variants.CHARACTERISTIC_COUNT):
            start = Variants.CHARACTERISTICS_START + Variants.CHARACTERISTIC_WIDTH * index
            result[f"{index + 3:02d}"] = text(row[start : start + Variants.CHARACTERISTIC_WIDTH])
        return result

    def _read_frame_ranges(self, region: str, code: str, group: str) -> tuple[FrameRange, ...]:
        layout = FrameRanges
        path = self.catalog_path(region, layout.PREFIX, layout.EXTENSION, code)
        key = group.encode().ljust(layout.KEY_WIDTH)
        return tuple(
            (
                text(row[layout.START_FRAME]),
                text(row[layout.START_SERIAL]),
                text(row[layout.END_FRAME]),
                text(row[layout.END_SERIAL]),
            )
            for _, row in keyed_records(path, layout.WIDTH, key)
        )

    def _read_thumbnail_index(self, region: str, code: str) -> dict[str, tuple[int, int]]:
        path = self.catalog_path(region, Thumbnails.PREFIX, Thumbnails.INDEX_EXTENSION, code)
        if not path.exists():
            return {}
        data = path.read_bytes()
        return {
            text(data[offset : offset + ImageIndex.KEY_WIDTH]): struct.unpack_from(
                ImageIndex.POINTER, data, offset + ImageIndex.POINTER_OFFSET
            )
            for offset in range(0, len(data), ImageIndex.WIDTH)
        }

    def _find_image_files(self, region: str) -> tuple[Path, ...]:
        return tuple(sorted((self.root / region).glob(Diagrams.INDEX_PATTERN)))

    def _render_diagram(self, region: str, image: str) -> bytes | None:
        key = image.encode().ljust(ImageIndex.KEY_WIDTH)
        for index in self._image_files(region):
            entry = next(keyed_records(index, ImageIndex.WIDTH, key), None)
            if entry is None:
                continue
            offset, size = struct.unpack_from(ImageIndex.POINTER, entry[1], ImageIndex.POINTER_OFFSET)
            if not 0 < size < Diagrams.MAX_BLOCK_SIZE:
                raise FormatError("Invalid illustration block size")
            with index.with_suffix(Diagrams.DATA_EXTENSION).open("rb") as stream:
                stream.seek(offset - 1)
                record = stream.read(size)
            return self._decode_diagram(record)
        return None

    @staticmethod
    def _decode_diagram(record: bytes) -> bytes:
        if (
            len(record) < Diagrams.HEADER_SIZE
            or record[Diagrams.VERSION] not in Diagrams.SUPPORTED_VERSIONS
            or record[Diagrams.COMPRESSION] != Diagrams.GROUP4
        ):
            raise FormatError("Unsupported EPC illustration encoding")
        width = int.from_bytes(record[Diagrams.WIDTH], "big")
        height = int.from_bytes(record[Diagrams.HEIGHT], "big")
        length = int.from_bytes(record[Diagrams.LENGTH], "big")
        if (
            not width
            or not height
            or width * height > Diagrams.MAX_PIXELS
            or Diagrams.HEADER_SIZE + length > len(record)
        ):
            raise FormatError("Invalid illustration dimensions or payload")
        payload = record[Diagrams.HEADER_SIZE : Diagrams.HEADER_SIZE + length]
        output = io.BytesIO()
        with Image.open(io.BytesIO(_group4_tiff(width, height, payload))) as bitmap:
            bitmap.save(output, format="PNG")
        return output.getvalue()
