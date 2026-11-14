from typing import Any

from fastapi import APIRouter

from epc.api import schemas
from epc.api.dependencies import Database, Limit, Native, Offset
from epc.errors import UnavailableError
from epc.importer import SCHEMA_VERSION
from epc.services import catalogs

router = APIRouter()


@router.get("/health", tags=["system"], response_model=schemas.Health)
def health(db: Database, native: Native) -> dict[str, str]:
    row = db.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
    if not row or row[0] != SCHEMA_VERSION or not native.root.is_dir():
        raise UnavailableError("Full EPC sources/index not ready")
    return {"status": "ok", "schema_version": SCHEMA_VERSION}


@router.get("/stats", tags=["system"], response_model=schemas.Stats)
def stats(db: Database) -> dict[str, Any]:
    return catalogs.statistics(db)


@router.get("/sources", tags=["provenance"], response_model=schemas.Page[schemas.SourceFile])
def sources(db: Database, limit: Limit = 25, offset: Offset = 0) -> dict[str, Any]:
    return catalogs.list_sources(db, limit, offset)


@router.get("/import-issues", tags=["provenance"], response_model=schemas.Page[schemas.ImportIssue])
def import_issues(db: Database, limit: Limit = 25, offset: Offset = 0) -> dict[str, Any]:
    return catalogs.list_import_issues(db, limit, offset)
