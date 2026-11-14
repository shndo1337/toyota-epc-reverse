import json
import sqlite3
from typing import Any

from epc.errors import InvalidRequestError, NotFoundError
from epc.services.search import like_pattern

Record = dict[str, Any]
Page = dict[str, Any]

_PRIVATE_COLUMNS = frozenset({"hnb_path"})


def page(items: list[Record], total: int, limit: int, offset: int, **extra: Any) -> Page:
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
        **extra,
    }


def public_catalog(row: sqlite3.Row | Record) -> Record:
    return {key: value for key, value in dict(row).items() if key not in _PRIVATE_COLUMNS}


def get_catalog(db: sqlite3.Connection, code: str) -> Record:
    rows = db.execute("SELECT * FROM catalogs WHERE code = ? OR local_code = ?", (code, code)).fetchall()
    if not rows:
        raise NotFoundError("Catalog not found")
    if len(rows) > 1:
        raise InvalidRequestError(f"Specify the market, for example EU:{code}")
    return dict(rows[0])


def statistics(db: sqlite3.Connection) -> Record:
    metadata: Record = dict(db.execute("SELECT key, value FROM metadata").fetchall())
    metadata.pop("source_root", None)
    metadata["counts"] = json.loads(metadata["counts"])
    metadata["regions"] = [
        dict(row)
        for row in db.execute(
            "SELECT region, count(*) AS catalogs, sum(application_count) AS applications "
            "FROM catalogs GROUP BY region"
        )
    ]
    return metadata


def list_sources(db: sqlite3.Connection, limit: int, offset: int) -> Page:
    total = db.execute("SELECT count(*) FROM source_files").fetchone()[0]
    rows = db.execute("SELECT * FROM source_files ORDER BY id LIMIT ? OFFSET ?", (limit, offset))
    return page([dict(row) for row in rows], total, limit, offset)


def list_import_issues(db: sqlite3.Connection, limit: int, offset: int) -> Page:
    total = db.execute("SELECT count(*) FROM import_issues").fetchone()[0]
    rows = db.execute("SELECT * FROM import_issues ORDER BY rowid LIMIT ? OFFSET ?", (limit, offset))
    return page([dict(row) for row in rows], total, limit, offset)


def list_catalogs(db: sqlite3.Connection, query: str, region: str | None, limit: int, offset: int) -> Page:
    conditions, args = [], []
    if region:
        conditions.append("region = ?")
        args.append(region)
    if query.strip():
        conditions.append(
            "(name LIKE ? ESCAPE '\\' OR model_codes LIKE ? ESCAPE '\\' OR local_code LIKE ? ESCAPE '\\')"
        )
        args.extend([like_pattern(query.strip())] * 3)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    total = db.execute(f"SELECT count(*) FROM catalogs{where}", args).fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM catalogs{where} ORDER BY region, name, local_code LIMIT ? OFFSET ?",
        [*args, limit, offset],
    )
    return page([public_catalog(row) for row in rows], total, limit, offset)


def catalog_detail(db: sqlite3.Connection, code: str) -> Record:
    catalog = get_catalog(db, code)
    item = public_catalog(catalog)
    item["part_count"] = db.execute(
        "SELECT count(DISTINCT number) FROM bindings WHERE catalog_id = ?", (catalog["id"],)
    ).fetchone()[0]
    return item


def list_variants(db: sqlite3.Connection, code: str, query: str, limit: int, offset: int) -> Page:
    catalog = get_catalog(db, code)
    pattern = like_pattern(query)
    where = " WHERE catalog_id = ? AND (model LIKE ? ESCAPE '\\' OR engine LIKE ? ESCAPE '\\')"
    args = [catalog["id"], pattern, pattern]
    total = db.execute(f"SELECT count(*) FROM variants{where}", args).fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM variants{where} ORDER BY model, id LIMIT ? OFFSET ?", [*args, limit, offset]
    )
    return page([dict(row) for row in rows], total, limit, offset)


def list_figures(db: sqlite3.Connection, code: str, limit: int, offset: int) -> Page:
    catalog = get_catalog(db, code)
    total = db.execute(
        "SELECT count(*) FROM catalog_figures WHERE catalog_id = ?", (catalog["id"],)
    ).fetchone()[0]
    rows = db.execute(
        "SELECT cf.code, f.name, cf.part_count FROM catalog_figures cf "
        "LEFT JOIN figures f ON f.region = ? AND f.code = cf.code "
        "WHERE catalog_id = ? ORDER BY cf.code LIMIT ? OFFSET ?",
        (catalog["region"], catalog["id"], limit, offset),
    )
    return page([dict(row) for row in rows], total, limit, offset)
