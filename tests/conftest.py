from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from epc.api import create_app
from epc.importer import build
from tests.samples import write_epc_root


@pytest.fixture
def epc_root(tmp_path: Path) -> Path:
    root = tmp_path / "epcdata"
    write_epc_root(root)
    return root


@pytest.fixture
def database(epc_root: Path, tmp_path: Path) -> Path:
    path = tmp_path / "index.sqlite"
    build(epc_root, path, ["EU"])
    return path


@pytest.fixture
def client(database: Path, epc_root: Path) -> Iterator[TestClient]:
    with TestClient(create_app(database, epc_root)) as test_client:
        yield test_client
