import json
import sqlite3
from pathlib import Path
from typing import Any

from epc.errors import NotFoundError
from epc.native import NativeCatalog
from epc.services.catalogs import Page, Record, get_catalog, page
from epc.services.search import like_pattern, parse_text_query
from epc.services.vehicles import exact_matches

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
_IN_PRODUCTION = (
    "(production_from IS NULL OR production_from <= ?) AND (production_to IS NULL OR production_to >= ?)"
)


def search_accessories(
    db: sqlite3.Connection,
    native: NativeCatalog,
    *,
    query: str,
    model: str | None,
    vehicle: str | None,
    catalog_code: str | None,
    production_month: str | None,
    limit: int,
    offset: int,
) -> Page:
    conditions: list[str] = []
    args: list[Any] = []

    text_query = parse_text_query(query)
    if text_query and text_query.number_prefix:
        conditions.append("number >= ? AND number < ?")
        args.extend(text_query.number_range)
    elif text_query and text_query.words:
        conditions.append("id IN (SELECT rowid FROM accessories_search WHERE accessories_search MATCH ?)")
        args.append(text_query.fts_expression)
    elif text_query:
        conditions.append("0")

    if model:
        conditions.append("model_codes LIKE ? ESCAPE '\\'")
        args.append(like_pattern(model))
    if catalog_code:
        catalog = get_catalog(db, catalog_code)
        patterns = [
            code.strip().replace("#", "_") for code in catalog["model_codes"].split(",") if code.strip()
        ]
        if patterns:
            conditions.append("(" + " OR ".join("model_codes LIKE ?" for _ in patterns) + ")")
            args.extend(f"%{pattern}%" for pattern in patterns)
    if production_month:
        conditions.append(_IN_PRODUCTION)
        args.extend([production_month, production_month])
    if vehicle:
        matches = exact_matches(db, native, vehicle)
        conditions.append(
            "(" + " OR ".join(f"(model_codes LIKE ? ESCAPE '\\' AND {_IN_PRODUCTION})" for _ in matches) + ")"
        )
        for match in matches:
            month = match["vehicle"]["production_month"]
            args.extend([like_pattern(match["model"]), month, month])

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    total = db.execute(f"SELECT count(*) FROM accessories{where}", args).fetchone()[0]
    rows = db.execute(
        "SELECT id AS accessory_id, number, name, title, model_codes "
        f"FROM accessories{where} ORDER BY number, id LIMIT ? OFFSET ?",
        [*args, limit, offset],
    )
    items = [{**dict(row), "display_number": row["number"], "catalog_count": 0} for row in rows]
    return page(items, total, limit, offset, next_offset=offset + limit)


def accessory_detail(db: sqlite3.Connection, identifier: int) -> Record:
    row = db.execute("SELECT * FROM accessories WHERE id = ?", (identifier,)).fetchone()
    if not row:
        raise NotFoundError("Accessory not found")
    item = dict(row)
    item["raw_fields"] = json.loads(item["raw_fields"])
    item["image_url"] = f"/api/v1/accessories/{identifier}/image" if item["image"] else None
    return item


def accessory_image(db: sqlite3.Connection, native: NativeCatalog, identifier: int) -> Path:
    row = db.execute("SELECT source_path, image FROM accessories WHERE id = ?", (identifier,)).fetchone()
    if not row or not row["image"]:
        raise NotFoundError("Accessory image not available")
    try:
        path = native.path(str(Path(row["source_path"]).parent / row["image"]))
    except ValueError as error:
        raise NotFoundError("Accessory image not available") from error
    if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
        raise NotFoundError("Accessory image not available")
    return path
