from typing import Any

from fastapi import APIRouter

from epc.api import schemas
from epc.api.dependencies import Counter, Database, Limit, Month, Native, Offset, Region, SearchText
from epc.services import parts
from epc.services.parts import PartFilters

router = APIRouter(tags=["parts"])


@router.get("/parts", response_model=schemas.ScanPage[schemas.PartSummary])
def search_parts(
    db: Database,
    native: Native,
    counter: Counter,
    q: SearchText = "",
    region: Region = None,
    catalog_code: str | None = None,
    figure_code: str | None = None,
    pnc: str | None = None,
    vehicle: str | None = None,
    model: str | None = None,
    engine: str | None = None,
    production_month: Month = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> dict[str, Any]:
    filters = PartFilters(q, region, catalog_code, figure_code, pnc, vehicle, model, engine, production_month)
    return parts.search_parts(db, native, counter, filters, limit=limit, offset=offset)


@router.get("/parts/{number}", response_model=schemas.PartDetail)
def part(number: str, db: Database, native: Native) -> dict[str, Any]:
    return parts.part_detail(db, native, number)


@router.get("/parts/{number}/applications", response_model=schemas.Page[schemas.Application])
def applications(
    number: str,
    db: Database,
    native: Native,
    catalog_code: str | None = None,
    vehicle: str | None = None,
    production_month: Month = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> dict[str, Any]:
    return parts.part_applications(
        db,
        native,
        number,
        catalog_code=catalog_code,
        vehicle=vehicle,
        production_month=production_month,
        limit=limit,
        offset=offset,
    )


@router.get("/applications/{identifier}", tags=["provenance"], response_model=schemas.ApplicationSource)
def application_source(identifier: str, db: Database, native: Native) -> dict[str, Any]:
    return parts.application_source(db, native, identifier)
