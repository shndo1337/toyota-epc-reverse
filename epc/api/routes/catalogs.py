from typing import Any

from fastapi import APIRouter, Response

from epc.api import schemas
from epc.api.dependencies import Database, Limit, Month, Native, Offset, Region, SearchText
from epc.services import catalogs, illustrations

router = APIRouter(prefix="/catalogs")

_IMAGE_CACHE = {"Cache-Control": "public, max-age=86400"}


@router.get("", tags=["catalogs"], response_model=schemas.Page[schemas.Catalog])
def list_catalogs(
    db: Database, q: SearchText = "", region: Region = None, limit: Limit = 25, offset: Offset = 0
) -> dict[str, Any]:
    return catalogs.list_catalogs(db, q, region, limit, offset)


@router.get("/{code}", tags=["catalogs"], response_model=schemas.CatalogDetail)
def catalog(code: str, db: Database) -> dict[str, Any]:
    return catalogs.catalog_detail(db, code)


@router.get("/{code}/variants", tags=["vehicles"], response_model=schemas.Page[schemas.Variant])
def variants(
    code: str, db: Database, q: SearchText = "", limit: Limit = 25, offset: Offset = 0
) -> dict[str, Any]:
    return catalogs.list_variants(db, code, q, limit, offset)


@router.get("/{code}/figures", tags=["catalogs"], response_model=schemas.Page[schemas.Figure])
def figures(code: str, db: Database, limit: Limit = 25, offset: Offset = 0) -> dict[str, Any]:
    return catalogs.list_figures(db, code, limit, offset)


@router.get("/{code}/figures/{figure}/images", tags=["illustrations"], response_model=schemas.FigureImages)
def figure_images(
    code: str,
    figure: str,
    db: Database,
    native: Native,
    production_month: Month = None,
    vehicle: str | None = None,
) -> dict[str, Any]:
    images = illustrations.figure_images(
        db, native, code, figure, production_month=production_month, vehicle=vehicle
    )
    return {"items": images}


@router.get(
    "/{code}/images/{image}.png",
    tags=["illustrations"],
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def thumbnail(code: str, image: str, db: Database, native: Native) -> Response:
    data = illustrations.thumbnail(db, native, code, image)
    return Response(data, media_type="image/png", headers=_IMAGE_CACHE)


@router.get(
    "/{code}/diagrams/{image}.png",
    tags=["illustrations"],
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def diagram(code: str, image: str, db: Database, native: Native) -> Response:
    data = illustrations.diagram(db, native, code, image)
    return Response(data, media_type="image/png", headers=_IMAGE_CACHE)
