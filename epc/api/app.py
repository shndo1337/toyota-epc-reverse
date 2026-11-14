import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from epc import __version__
from epc.api.routes import accessories, catalogs, parts, system, vehicles
from epc.config import Settings
from epc.errors import CatalogError, InvalidRequestError, NotFoundError, UnavailableError
from epc.native import NativeCatalog
from epc.services.parts import PartCounter

STATIC = Path(__file__).resolve().parent.parent / "static"
API_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)

_STATUS: dict[type[CatalogError], int] = {NotFoundError: 404, InvalidRequestError: 422, UnavailableError: 503}


def create_app(database: Path | str | None = None, source_root: Path | str | None = None) -> FastAPI:
    settings = Settings.load(database, source_root)
    app = FastAPI(
        title="Toyota EPC",
        version=__version__,
        description=(
            "Local Toyota EPC 2025.01 catalog for all ISO markets: indexed number, name and catalog "
            "search, native VIN and frame lookup, illustrations and source provenance."
        ),
    )
    app.state.settings = settings
    app.state.native = NativeCatalog(settings.source_root)
    app.state.part_counter = PartCounter(settings.database)

    app.exception_handler(CatalogError)(_catalog_error)
    app.exception_handler(sqlite3.DatabaseError)(_database_error)
    app.middleware("http")(_server_timing)

    for router in (system.router, catalogs.router, vehicles.router, parts.router, accessories.router):
        app.include_router(router, prefix=API_PREFIX)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.add_api_route("/", _index, include_in_schema=False)
    return app


def _index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


async def _catalog_error(request: Request, error: CatalogError) -> JSONResponse:
    return JSONResponse(status_code=_STATUS.get(type(error), 500), content={"detail": error.detail})


async def _database_error(request: Request, error: sqlite3.DatabaseError) -> JSONResponse:
    logger.exception("EPC database error", exc_info=error)
    return JSONResponse(status_code=503, content={"detail": "EPC database is unavailable"})


async def _server_timing(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - started) * 1000:.2f}"
    return response
