import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from epc.errors import InvalidRequestError, NotFoundError
from epc.layout import XOR_MASK, PartRecords, text
from epc.native import NativeCatalog
from epc.services.catalogs import Page, Record, get_catalog, page, public_catalog
from epc.services.fitment import fits
from epc.services.search import display_number, like_pattern, parse_part_number, parse_text_query
from epc.services.vehicles import exact_matches

SCAN_LIMIT = 2048
FITMENT_BATCH = 128
_APPLICATION_ID = re.compile(r"(EU|GR|JP|US):([A-Z0-9]{6}):(\d+)")
_VARIANT_FILTER = (
    "b.catalog_id IN (SELECT catalog_id FROM variants "
    "WHERE model LIKE ? ESCAPE '\\' AND engine LIKE ? ESCAPE '\\')"
)
_NAME_MATCH = "b.pnc IN (SELECT pnc FROM names_search WHERE names_search MATCH ?)"


@dataclass(frozen=True)
class PartFilters:
    query: str = ""
    region: str | None = None
    catalog_code: str | None = None
    figure_code: str | None = None
    pnc: str | None = None
    vehicle: str | None = None
    model: str | None = None
    engine: str | None = None
    production_month: str | None = None


@dataclass
class PartQuery:
    clause: str
    args: tuple[Any, ...]
    joined: bool
    variants: dict[int, list[Record]] = field(default_factory=dict)


class PartCounter:
    def __init__(self, database: Path) -> None:
        self._uri = database.as_uri() + "?mode=ro"
        self._count = lru_cache(maxsize=128)(self._query)

    def __call__(self, query: PartQuery) -> int:
        return self._count(query.clause, query.args, query.joined)

    def _query(self, clause: str, args: tuple[Any, ...], joined: bool) -> int:
        selection = "count(DISTINCT p.number)" if joined else "count(*)"
        with closing(sqlite3.connect(self._uri, uri=True)) as db:
            return int(db.execute(f"SELECT {selection}{clause}", args).fetchone()[0])


@dataclass
class _Conditions:
    sql: list[str] = field(default_factory=list)
    args: list[Any] = field(default_factory=list)
    joined: bool = False

    def add(self, condition: str, *args: Any, join: bool = True) -> None:
        self.sql.append(condition)
        self.args.extend(args)
        self.joined = self.joined or join

    def query(self, variants: dict[int, list[Record]]) -> PartQuery:
        clause = " FROM parts p"
        if self.joined:
            clause += " JOIN bindings b ON b.number = p.number JOIN catalogs c ON c.id = b.catalog_id"
        if self.sql:
            clause += " WHERE " + " AND ".join(self.sql)
        return PartQuery(clause, tuple(self.args), self.joined, variants)


def build_part_query(db: sqlite3.Connection, native: NativeCatalog, filters: PartFilters) -> PartQuery:
    if filters.figure_code and not filters.catalog_code:
        raise InvalidRequestError("figure_code requires catalog_code")
    where = _Conditions()
    if filters.catalog_code:
        where.add("b.catalog_id = ?", get_catalog(db, filters.catalog_code)["id"])
    if filters.region:
        where.add("c.region = ?", filters.region)
    if filters.figure_code:
        where.add("b.figure = ?", filters.figure_code)
    if filters.pnc:
        where.add("b.pnc = ?", filters.pnc)
    if filters.model or filters.engine:
        where.add(_VARIANT_FILTER, like_pattern(filters.model or ""), like_pattern(filters.engine or ""))
    variants: dict[int, list[Record]] = {}
    if filters.vehicle:
        for variant in exact_matches(db, native, filters.vehicle, filters.region):
            variants.setdefault(variant["catalog_id"], []).append(variant)
        where.add(f"b.catalog_id IN ({', '.join('?' * len(variants))})", *variants)
    _add_text_condition(where, filters.query)
    return where.query(variants)


def _add_text_condition(where: _Conditions, value: str) -> None:
    text_query = parse_text_query(value)
    if text_query is None:
        return
    if text_query.number_prefix:
        where.add("p.number >= ? AND p.number < ?", *text_query.number_range, join=False)
    elif text_query.words:
        where.add(_NAME_MATCH, text_query.fts_expression)
    else:
        where.add("0", join=False)


def search_parts(
    db: sqlite3.Connection,
    native: NativeCatalog,
    counter: PartCounter,
    filters: PartFilters,
    *,
    limit: int,
    offset: int,
) -> Page:
    query = build_part_query(db, native, filters)
    total = counter(query)
    if query.variants or filters.production_month:
        return _scan_applicable(
            db,
            native,
            query,
            production_month=filters.production_month,
            total=total,
            limit=limit,
            offset=offset,
        )
    rows = db.execute(_select_page(query), [*query.args, limit + 1, offset]).fetchall()
    items = [_summary(db, row) for row in rows[:limit]]
    has_more = len(rows) > limit
    return _result(items, total, limit, offset, has_more=has_more, next_offset=offset + limit, estimate=False)


def _scan_applicable(
    db: sqlite3.Connection,
    native: NativeCatalog,
    query: PartQuery,
    *,
    production_month: str | None,
    total: int,
    limit: int,
    offset: int,
) -> Page:
    items: list[Record] = []
    position = offset
    while position - offset < SCAN_LIMIT:
        rows = db.execute(_select_page(query), [*query.args, FITMENT_BATCH, position]).fetchall()
        for row in rows:
            candidate = position
            position += 1
            if not _is_applicable(db, native, row["number"], query.variants, production_month):
                continue
            if len(items) == limit:
                return _result(
                    items, total, limit, offset, has_more=True, next_offset=candidate, estimate=True
                )
            items.append(_summary(db, row))
        if len(rows) < FITMENT_BATCH:
            break
    truncated = position < total and position - offset >= SCAN_LIMIT
    next_offset = position if truncated else offset
    return _result(items, total, limit, offset, has_more=truncated, next_offset=next_offset, estimate=True)


def _select_page(query: PartQuery) -> str:
    return f"SELECT DISTINCT p.number, p.catalog_count{query.clause} ORDER BY p.number LIMIT ? OFFSET ?"


def part_detail(db: sqlite3.Connection, native: NativeCatalog, value: str) -> Record:
    number = _existing_part(db, value)
    catalogs = [
        public_catalog(row)
        for row in db.execute(
            "SELECT DISTINCT c.* FROM bindings b JOIN catalogs c ON c.id = b.catalog_id "
            "WHERE b.number = ? ORDER BY c.code",
            (number,),
        )
    ]
    names = [
        dict(row)
        for row in db.execute(
            "SELECT DISTINCT b.pnc, n.name FROM bindings b JOIN catalogs c ON c.id = b.catalog_id "
            "LEFT JOIN part_names n ON n.region = c.region AND n.pnc = b.pnc "
            "WHERE b.number = ? ORDER BY b.pnc, n.name",
            (number,),
        )
    ]
    regions = list(dict.fromkeys(catalog["region"] for catalog in catalogs))
    return {
        "number": number,
        "names": names,
        "catalogs": catalogs,
        "list_price": native.price(number),
        "related_numbers": native.related_numbers(number, regions),
    }


def part_applications(
    db: sqlite3.Connection,
    native: NativeCatalog,
    value: str,
    *,
    catalog_code: str | None,
    vehicle: str | None,
    production_month: str | None,
    limit: int,
    offset: int,
) -> Page:
    number = _existing_part(db, value)
    catalog_id = get_catalog(db, catalog_code)["id"] if catalog_code else None
    variants: list[Record | None] = list(exact_matches(db, native, vehicle)) if vehicle else []
    items = list(binding_applications(db, native, number, catalog_id))
    if variants or production_month:
        items = [
            item
            for item in items
            if any(
                (not variant or variant["catalog_code"] == item["catalog_code"])
                and fits(native, item, variant, production_month or _vehicle_month(variant))
                for variant in variants or [None]
            )
        ]
    return page(items[offset : offset + limit], len(items), limit, offset)


def application_source(db: sqlite3.Connection, native: NativeCatalog, identifier: str) -> Record:
    match = _APPLICATION_ID.fullmatch(identifier)
    if not match:
        raise InvalidRequestError("Expected REGION:CATALOG:OFFSET")
    region, code, offset = match[1], match[2], int(match[3])
    get_catalog(db, f"{region}:{code}")
    raw = native.read_part_record(region, code, offset)
    if raw is None:
        raise NotFoundError("Source record not found")
    pnc = text(raw[PartRecords.PNC])
    header = next((a for a in native.applications(region, code, pnc) if a["source_offset"] == offset), None)
    if header is None:
        raise NotFoundError("Application header not found")
    source = db.execute("SELECT sha256 FROM source_files WHERE path = ?", (header["source_path"],)).fetchone()
    return {
        **header,
        "source_sha256": source[0],
        "record_size": PartRecords.WIDTH,
        "xor_mask": XOR_MASK,
    }


def binding_applications(
    db: sqlite3.Connection, native: NativeCatalog, number: str, catalog_id: int | None = None
) -> Iterator[Record]:
    sql = (
        "SELECT DISTINCT c.code, c.local_code, c.region, c.name, b.pnc, n.name AS part_name "
        "FROM bindings b JOIN catalogs c ON c.id = b.catalog_id "
        "LEFT JOIN part_names n ON n.region = c.region AND n.pnc = b.pnc WHERE b.number = ?"
    )
    args: list[Any] = [number]
    if catalog_id is not None:
        sql += " AND b.catalog_id = ?"
        args.append(catalog_id)
    for binding in db.execute(sql + " ORDER BY c.code, b.pnc", args).fetchall():
        for application in native.applications(binding["region"], binding["local_code"], binding["pnc"]):
            if application["part_number"] == number:
                yield {**application, "catalog_name": binding["name"], "name": binding["part_name"]}


def _existing_part(db: sqlite3.Connection, value: str) -> str:
    number = parse_part_number(value)
    if not db.execute("SELECT 1 FROM parts WHERE number = ?", (number,)).fetchone():
        raise NotFoundError("Part not found")
    return number


def _vehicle_month(variant: Record | None) -> str | None:
    return variant["vehicle"]["production_month"] if variant else None


def _is_applicable(
    db: sqlite3.Connection,
    native: NativeCatalog,
    number: str,
    variants: dict[int, list[Record]],
    production_month: str | None,
) -> bool:
    catalogs: dict[int, list[Record]] = variants or {
        catalog_id: []
        for (catalog_id,) in db.execute(
            "SELECT DISTINCT catalog_id FROM bindings WHERE number = ?", (number,)
        )
    }
    candidates: list[Record | None]
    for catalog_id, catalog_variants in catalogs.items():
        candidates = list(catalog_variants) or [None]
        for application in binding_applications(db, native, number, catalog_id):
            for variant in candidates:
                if fits(native, application, variant, production_month or _vehicle_month(variant)):
                    return True
    return False


def _summary(db: sqlite3.Connection, row: sqlite3.Row) -> Record:
    number = row["number"]
    name = db.execute(
        "SELECT n.name FROM bindings b JOIN catalogs c ON c.id = b.catalog_id "
        "LEFT JOIN part_names n ON n.region = c.region AND n.pnc = b.pnc "
        "WHERE b.number = ? ORDER BY b.catalog_id, b.pnc LIMIT 1",
        (number,),
    ).fetchone()
    return {
        "number": number,
        "display_number": display_number(number),
        "name": name[0] if name else None,
        "catalog_count": row["catalog_count"],
    }


def _result(
    items: list[Record],
    total: int,
    limit: int,
    offset: int,
    *,
    has_more: bool,
    next_offset: int,
    estimate: bool,
) -> Page:
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "next_offset": next_offset,
        "total_is_estimate": estimate,
    }
