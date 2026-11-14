import sqlite3
from collections.abc import Iterator
from contextlib import closing
from typing import Annotated

from fastapi import Depends, Query, Request

from epc.errors import UnavailableError
from epc.native import NativeCatalog
from epc.services.parts import PartCounter

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=20_000_000)]
Month = Annotated[str | None, Query(pattern=r"^(19|20)\d{2}-(0[1-9]|1[0-2])$")]
Region = Annotated[str | None, Query(pattern=r"^(EU|GR|JP|US)$")]
SearchText = Annotated[str, Query(max_length=100)]


def connect(request: Request) -> Iterator[sqlite3.Connection]:
    path = request.app.state.settings.database
    if not path.is_file():
        raise UnavailableError("Build the catalog index first: python -m epc.importer")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, check_same_thread=False)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only = ON")
        db.execute("PRAGMA cache_size = -16384")
        yield db


def native_catalog(request: Request) -> NativeCatalog:
    catalog: NativeCatalog = request.app.state.native
    return catalog


def part_counter(request: Request) -> PartCounter:
    counter: PartCounter = request.app.state.part_counter
    return counter


Database = Annotated[sqlite3.Connection, Depends(connect)]
Native = Annotated[NativeCatalog, Depends(native_catalog)]
Counter = Annotated[PartCounter, Depends(part_counter)]
