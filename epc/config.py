import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATABASE = Path("data/full.sqlite")
DEFAULT_SOURCE_ROOT = Path("data/full/app/epcdata")


@dataclass(frozen=True)
class Settings:
    database: Path
    source_root: Path

    @classmethod
    def load(cls, database: Path | str | None = None, source_root: Path | str | None = None) -> "Settings":
        database_path = Path(database or os.environ.get("EPC_DATABASE") or DEFAULT_DATABASE).resolve()
        root = source_root or os.environ.get("EPC_SOURCE_ROOT") or _recorded_source_root(database_path)
        return cls(database_path, Path(root or DEFAULT_SOURCE_ROOT).resolve())


def _recorded_source_root(database: Path) -> Path | None:
    if not database.is_file():
        return None
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT value FROM metadata WHERE key = 'source_root'").fetchone()
    return database.parent / row[0] if row else None
