import argparse
import csv
import hashlib
import io
import json
import logging
import os
import sqlite3
import tempfile
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from epc.layout import (
    ENCODING,
    REGIONS,
    XOR_MASK,
    Catalogs,
    FigureBindings,
    FigureNames,
    FormatError,
    PartNames,
    PartRecords,
    Variants,
    VehicleBlocks,
    catalog_file,
    month,
    text,
    unmask,
)
from epc.records import split_records

SCHEMA_VERSION = "2"
DATASET = "Toyota EPC 2025.01"
SCOPE = "All catalogs and native VIN/frame blocks from the local ISO"
ACCESSORY_FOLDER = "JPIO"
ACCESSORY_MIN_FIELDS = 12

logger = logging.getLogger(__name__)

_INDEXES = (
    "CREATE INDEX bindings_number ON bindings(number, catalog_id, pnc, figure)",
    "CREATE INDEX bindings_catalog ON bindings(catalog_id, figure, number, pnc)",
    "CREATE INDEX bindings_pnc ON bindings(pnc, number, catalog_id)",
    "CREATE INDEX variants_vin ON variants(vin_prefix, catalog_id)",
    "CREATE INDEX variants_frame ON variants(frame, model, catalog_id)",
    "CREATE INDEX variants_catalog ON variants(catalog_id, model)",
)
_INSERT_VARIANT = (
    "INSERT INTO variants(catalog_id, vin_prefix, model, frame, source_group, variant_code, "
    "production_from, production_to, engine, attributes, source_path, source_offset) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_INSERT_ACCESSORY = (
    "INSERT INTO accessories(group_code, document, title, production_from, production_to, name, number, "
    "destination, quantity, notes, model_codes, image, source_path, source_row, raw_fields) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def build(root: Path, target: Path, regions: Sequence[str] = REGIONS) -> dict[str, int]:
    root, target = root.resolve(), target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".full-import-", suffix=".sqlite", dir=target.parent)
    os.close(descriptor)
    db = sqlite3.connect(temporary)
    try:
        counts = _IndexBuilder(db, root, target, tuple(regions)).run()
        db.close()
        os.replace(temporary, target)
        return counts
    except BaseException:
        db.close()
        Path(temporary).unlink(missing_ok=True)
        raise


class _IndexBuilder:
    def __init__(self, db: sqlite3.Connection, root: Path, target: Path, regions: tuple[str, ...]) -> None:
        self.db = db
        self.root = root
        self.target = target
        self.regions = regions
        self.started = perf_counter()
        self.counts = dict.fromkeys(("catalogs", "applications", "source_records", "bindings", "variants"), 0)
        self.orphan_variants: list[tuple[str, bytes, str, int]] = []

    def run(self) -> dict[str, int]:
        self.db.execute("PRAGMA journal_mode = OFF")
        self.db.execute("PRAGMA synchronous = OFF")
        self.db.execute("PRAGMA temp_store = FILE")
        self.db.execute("PRAGMA cache_size = -196608")
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text())
        for region in self.regions:
            self._import_region(region)
            self.db.commit()
            logger.info("%s indexed in %.1f s: %s", region, self._elapsed(), self.counts)
        self._attach_orphan_variants()
        logger.info("Building search indexes")
        self._build_indexes()
        self._import_accessories()
        self._count_totals()
        self._count_vehicles()
        self._write_metadata()
        self.db.execute("ANALYZE")
        self.db.commit()
        if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise FormatError("SQLite quick_check failed")
        self.db.execute("UPDATE metadata SET value = ? WHERE key = 'build_seconds'", (self._seconds(),))
        self.db.commit()
        logger.info("Index complete in %s s", self._seconds())
        return self.counts

    def _register(self, path: Path, width: int, *, masked: bool = False, data: bytes | None = None) -> bytes:
        content = path.read_bytes() if data is None else data
        if len(content) % width:
            raise FormatError(f"{path}: {len(content)} bytes, expected record width {width}")
        self.db.execute(
            "INSERT OR IGNORE INTO source_files(path, sha256, size_bytes, record_size, xor_mask) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                self._relative(path),
                hashlib.sha256(content).hexdigest(),
                len(content),
                width,
                XOR_MASK if masked else 0,
            ),
        )
        return unmask(content) if masked else content

    def _import_region(self, region: str) -> None:
        folder = self.root / region
        catalogs = self._register(folder / Catalogs.FILE, Catalogs.WIDTH, masked=True)
        catalog_ids = {}
        for _, row in split_records(catalogs, Catalogs.WIDTH):
            code = text(row[Catalogs.CODE])
            catalog_ids[code] = self._import_catalog(region, folder, code, row)
        self._import_names(
            region, folder / PartNames.FILE, PartNames.WIDTH, PartNames.KEY_WIDTH, "part_names"
        )
        self._import_names(
            region, folder / FigureNames.FILE, FigureNames.WIDTH, FigureNames.KEY_WIDTH, "figures"
        )
        self._import_variants(region, folder, catalog_ids)

    def _import_catalog(self, region: str, folder: Path, code: str, row: bytes) -> int:
        path = folder / catalog_file(PartRecords.PREFIX, PartRecords.EXTENSION, code)
        if not path.is_file():
            raise FormatError(f"Missing catalog source: {path}")
        masked = path.read_bytes()
        records = self._register(path, PartRecords.WIDTH, masked=True, data=masked)
        keys = [
            records[offset : offset + PartRecords.PNC.stop]
            for offset in range(0, len(records), PartRecords.WIDTH)
        ]
        if keys != sorted(keys):
            raise FormatError(f"{path}: PNC order is not suitable for binary search")
        header_marker = PartRecords.HEADER[0] ^ XOR_MASK
        headers = bytes(memoryview(masked)[PartRecords.KIND_OFFSET :: PartRecords.WIDTH]).count(header_marker)
        record_count = len(masked) // PartRecords.WIDTH
        (catalog_id,) = self.db.execute(
            "INSERT INTO catalogs(code, local_code, region, name, model_codes, production_from, "
            "production_to, revision, imported, application_count, record_count, hnb_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?) RETURNING id",
            (
                f"{region}:{code}",
                code,
                region,
                text(row[Catalogs.NAME]),
                text(row[Catalogs.MODEL_CODES]),
                month(row[Catalogs.PRODUCTION_FROM]),
                month(row[Catalogs.PRODUCTION_TO]),
                month(row[Catalogs.REVISION]),
                headers,
                record_count,
                self._relative(path),
            ),
        ).fetchone()
        self.counts["catalogs"] += 1
        self.counts["applications"] += headers
        self.counts["source_records"] += record_count

        bindings = self._register(
            folder / catalog_file(FigureBindings.PREFIX, FigureBindings.EXTENSION, code), FigureBindings.WIDTH
        )
        self.db.executemany(
            "INSERT INTO bindings VALUES (?, ?, ?, ?)",
            (
                (
                    text(binding[FigureBindings.NUMBER]),
                    catalog_id,
                    text(binding[FigureBindings.PNC]),
                    text(binding[FigureBindings.FIGURE]),
                )
                for _, binding in split_records(bindings, FigureBindings.WIDTH)
            ),
        )
        self.counts["bindings"] += len(bindings) // FigureBindings.WIDTH
        return int(catalog_id)

    def _import_names(self, region: str, path: Path, width: int, key_width: int, table: str) -> None:
        data = self._register(path, width)
        self.db.executemany(
            f"INSERT INTO {table} VALUES (?, ?, ?)",
            ((region, text(row[:key_width]), text(row[key_width:])) for _, row in split_records(data, width)),
        )

    def _import_variants(self, region: str, folder: Path, catalog_ids: dict[str, int]) -> None:
        filename = (
            Variants.OVERSEAS_FILE if (folder / Variants.OVERSEAS_FILE).exists() else Variants.DOMESTIC_FILE
        )
        source = f"{region}/{filename}"
        data = self._register(folder / filename, Variants.WIDTH, masked=True)
        batch = []
        for offset, row in split_records(data, Variants.WIDTH):
            code = text(row[Variants.CATALOG_CODE])
            if code in catalog_ids:
                batch.append(_variant_values(catalog_ids[code], row, source, offset))
                continue
            self.db.execute(
                "INSERT INTO import_issues VALUES (?, ?, ?, ?)",
                (source, offset, f"Variant references catalog {code} absent from SHAMEI", row.hex()),
            )
            self.orphan_variants.append((code, row, source, offset))
        self.db.executemany(_INSERT_VARIANT, batch)
        self.counts["variants"] += len(batch)

    def _attach_orphan_variants(self) -> None:
        for code, row, source, offset in self.orphan_variants:
            for (catalog_id,) in self.db.execute(
                "SELECT id FROM catalogs WHERE local_code = ?", (code,)
            ).fetchall():
                self.db.execute(_INSERT_VARIANT, _variant_values(catalog_id, row, source, offset))
                self.counts["variants"] += 1

    def _build_indexes(self) -> None:
        for statement in _INDEXES:
            self.db.execute(statement)
        self.db.execute(
            "INSERT INTO parts SELECT number, count(DISTINCT catalog_id) FROM bindings GROUP BY number"
        )
        self.db.execute(
            "INSERT INTO catalog_figures "
            "SELECT catalog_id, figure, count(DISTINCT number) FROM bindings GROUP BY catalog_id, figure"
        )
        self.db.execute(
            "INSERT INTO names_search(region, pnc, name) SELECT region, pnc, name FROM part_names"
        )

    def _import_accessories(self) -> None:
        rows = [
            row
            for path in sorted((self.root / ACCESSORY_FOLDER).rglob("*"))
            if path.suffix.lower() == ".csv"
            for row in self._accessory_rows(path)
        ]
        self.db.executemany(_INSERT_ACCESSORY, rows)
        self.db.execute("INSERT INTO accessories_search(accessories_search) VALUES ('rebuild')")
        self.db.execute("CREATE INDEX accessories_number ON accessories(number)")
        self.db.execute("CREATE INDEX accessories_group ON accessories(group_code)")
        self.counts["accessories"] = len(rows)

    def _accessory_rows(self, path: Path) -> Iterable[tuple[Any, ...]]:
        raw = path.read_bytes()
        try:
            document = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            document = raw.decode(ENCODING, errors="replace")
        source = self._relative(path)
        for line, fields in enumerate(csv.reader(io.StringIO(document)), start=1):
            if len(fields) < ACCESSORY_MIN_FIELDS:
                continue
            yield (
                fields[0],
                fields[2],
                fields[3],
                month(fields[4].encode()),
                month(fields[5].encode()),
                fields[6],
                fields[7].replace("-", "").strip(),
                fields[8],
                fields[9],
                fields[10],
                fields[11],
                fields[12] if len(fields) > ACCESSORY_MIN_FIELDS else "",
                source,
                line,
                json.dumps(fields, ensure_ascii=False),
            )

    def _count_totals(self) -> None:
        count = self._scalar
        self.counts["parts"] = count("SELECT count(*) FROM parts")
        self.counts["part_names"] = count("SELECT count(*) FROM part_names")
        self.counts["figures"] = count("SELECT count(*) FROM figures")
        self.counts["imported_catalogs"] = self.counts["catalogs"]
        self.counts["application_texts"] = self.counts["source_records"] - self.counts["applications"]
        self.counts["import_issues"] = count("SELECT count(*) FROM import_issues")

    def _count_vehicles(self) -> None:
        blocks = vehicles = 0
        for domain in (VehicleBlocks.DOMESTIC, VehicleBlocks.OVERSEAS):
            for frame in (self.root / VehicleBlocks.FOLDER / domain).iterdir():
                if not frame.is_dir():
                    continue
                for entry in os.scandir(frame):
                    if not entry.name.endswith(VehicleBlocks.EXTENSION):
                        continue
                    size = entry.stat().st_size
                    if size % VehicleBlocks.WIDTH:
                        raise FormatError(f"{entry.path}: invalid vehicle block length")
                    blocks += 1
                    vehicles += size // VehicleBlocks.WIDTH
        self.counts["vehicle_blocks"] = blocks
        self.counts["vehicles"] = vehicles

    def _write_metadata(self) -> None:
        values = {
            "schema_version": SCHEMA_VERSION,
            "dataset": DATASET,
            "region": ",".join(self.regions),
            "source_root": os.path.relpath(self.root, self.target.parent),
            "scope": SCOPE,
            "counts": json.dumps(self.counts),
            "imported_at": datetime.now(UTC).isoformat(),
            "build_seconds": self._seconds(),
        }
        self.db.executemany("INSERT INTO metadata VALUES (?, ?)", values.items())

    def _scalar(self, sql: str) -> int:
        return int(self.db.execute(sql).fetchone()[0])

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _elapsed(self) -> float:
        return perf_counter() - self.started

    def _seconds(self) -> str:
        return str(round(self._elapsed(), 2))


def _variant_values(catalog_id: int, row: bytes, source: str, offset: int) -> tuple[Any, ...]:
    return (
        catalog_id,
        text(row[Variants.VIN_PREFIX]),
        text(row[Variants.MODEL]),
        text(row[Variants.FRAME]),
        text(row[Variants.SOURCE_GROUP]),
        text(row[Variants.VARIANT_CODE]),
        month(row[Variants.PRODUCTION_FROM]),
        month(row[Variants.PRODUCTION_TO]),
        text(row[Variants.ENGINE]),
        text(row[Variants.ATTRIBUTES]),
        source,
        offset,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the SQLite search index over extracted EPC data.")
    parser.add_argument("--source", type=Path, default=Path("data/full/app/epcdata"))
    parser.add_argument("--database", type=Path, default=Path("data/full.sqlite"))
    parser.add_argument("--regions", nargs="+", choices=REGIONS, default=list(REGIONS))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        counts = build(args.source, args.database, args.regions)
    except (FormatError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Import failed: {error}\n")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
