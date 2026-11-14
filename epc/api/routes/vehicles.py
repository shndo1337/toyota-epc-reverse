from typing import Annotated, Any

from fastapi import APIRouter, Query

from epc.api import schemas
from epc.api.dependencies import Database, Native, Region
from epc.errors import InvalidRequestError
from epc.services.vehicles import VIN, resolve_vehicle

router = APIRouter(tags=["vehicles"])


@router.get("/vehicles/resolve", response_model=schemas.VehicleResolution)
def resolve(
    db: Database,
    native: Native,
    identifier: Annotated[str, Query(min_length=8, max_length=30)],
    region: Region = None,
) -> dict[str, Any]:
    return resolve_vehicle(db, native, identifier, region)


@router.get("/vin/{vin}", response_model=schemas.VehicleResolution)
def vin(vin: str, db: Database, native: Native, region: Region = None) -> dict[str, Any]:
    if not VIN.fullmatch(vin.upper()):
        raise InvalidRequestError("Expected a 17-character VIN")
    return resolve_vehicle(db, native, vin, region)
