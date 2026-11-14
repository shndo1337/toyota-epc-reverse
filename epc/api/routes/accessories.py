from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse

from epc.api import schemas
from epc.api.dependencies import Database, Limit, Month, Native, Offset, SearchText
from epc.services import accessories

router = APIRouter(prefix="/accessories", tags=["accessories"])


@router.get("", response_model=schemas.ContinuationPage[schemas.AccessorySummary])
def search_accessories(
    db: Database,
    native: Native,
    q: SearchText = "",
    model: str | None = None,
    vehicle: str | None = None,
    catalog_code: str | None = None,
    production_month: Month = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> dict[str, Any]:
    return accessories.search_accessories(
        db,
        native,
        query=q,
        model=model,
        vehicle=vehicle,
        catalog_code=catalog_code,
        production_month=production_month,
        limit=limit,
        offset=offset,
    )


@router.get("/{identifier}", response_model=schemas.Accessory)
def accessory(identifier: int, db: Database) -> dict[str, Any]:
    return accessories.accessory_detail(db, identifier)


@router.get(
    "/{identifier}/image",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
def accessory_image(identifier: int, db: Database, native: Native) -> FileResponse:
    path = accessories.accessory_image(db, native, identifier)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
