import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from epc.importer import SCHEMA_VERSION, build
from epc.layout import FormatError, unmask


def rows(database: Path, sql: str) -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(database)) as db:
        return db.execute(sql).fetchall()


def test_index_contents(database: Path) -> None:
    assert rows(database, "SELECT code, name, application_count, record_count FROM catalogs") == [
        ("EU:101510", "TEST CAR", 2, 5)
    ]
    assert rows(database, "SELECT number, catalog_count FROM parts ORDER BY number") == [
        ("044650H020", 1),
        ("909150YZZE", 1),
    ]
    assert rows(database, "SELECT code, part_count FROM catalog_figures ORDER BY code") == [
        ("1502", 1),
        ("4705", 1),
    ]
    assert rows(database, "SELECT model, engine, frame FROM variants") == [("ABC10L-TEST", "1TEST", "ABC10")]
    assert rows(database, "SELECT number, model_codes FROM accessories") == [("PZ31042032C0", "ABC10L-TEST")]


def test_metadata_records_counts_and_source_root(database: Path, epc_root: Path) -> None:
    metadata: dict[str, str] = dict(rows(database, "SELECT key, value FROM metadata"))
    assert metadata["schema_version"] == SCHEMA_VERSION
    assert database.parent / metadata["source_root"] == epc_root
    counts = json.loads(metadata["counts"])
    assert counts["application_texts"] == 3
    assert counts["vehicles"] == 1
    assert counts["import_issues"] == 0


def test_source_files_carry_verifiable_hashes(database: Path, epc_root: Path) -> None:
    for path, sha256, size, xor_mask in rows(
        database, "SELECT path, sha256, size_bytes, xor_mask FROM source_files"
    ):
        content = (epc_root / path).read_bytes()
        assert hashlib.sha256(content).hexdigest() == sha256
        assert len(content) == size
        assert xor_mask in (0, 200)


def test_rebuild_is_deterministic(database: Path, epc_root: Path, tmp_path: Path) -> None:
    second = tmp_path / "second.sqlite"
    build(epc_root, second, ["EU"])
    for table in ("catalogs", "bindings", "parts", "variants", "source_files", "accessories"):
        assert rows(database, f"SELECT * FROM {table}") == rows(second, f"SELECT * FROM {table}")


def test_failed_build_keeps_the_previous_index(database: Path, epc_root: Path) -> None:
    previous = hashlib.sha256(database.read_bytes()).digest()
    records = epc_root / "EU" / "101510" / "HNB10151.ACD"
    records.write_bytes(records.read_bytes()[:-1])
    with pytest.raises(FormatError, match="expected record width 122"):
        build(epc_root, database, ["EU"])
    assert hashlib.sha256(database.read_bytes()).digest() == previous
    assert not list(database.parent.glob(".full-import-*"))


def test_unsorted_part_records_are_rejected(epc_root: Path, tmp_path: Path) -> None:
    records = epc_root / "EU" / "101510" / "HNB10151.ACD"
    data = unmask(records.read_bytes())
    records.write_bytes(unmask(data[-122:] + data[:-122]))
    target = tmp_path / "unsorted.sqlite"
    with pytest.raises(FormatError, match="binary search"):
        build(epc_root, target, ["EU"])
    assert not target.exists()


def test_variant_without_catalog_is_recorded(epc_root: Path, tmp_path: Path) -> None:
    variants = epc_root / "EU" / "JOHOJP.ACD"
    orphan = b"999999" + unmask(variants.read_bytes())[6:]
    variants.write_bytes(unmask(orphan))
    target = tmp_path / "orphan.sqlite"
    build(epc_root, target, ["EU"])
    assert rows(target, "SELECT reason FROM import_issues") == [
        ("Variant references catalog 999999 absent from SHAMEI",)
    ]
    assert rows(target, "SELECT count(*) FROM variants") == [(0,)]
