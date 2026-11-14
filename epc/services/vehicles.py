import re
import sqlite3
from typing import Any

from epc.errors import InvalidRequestError
from epc.layout import VehicleBlocks
from epc.native import NativeCatalog
from epc.services.fitment import in_production

Record = dict[str, Any]

VIN = re.compile(r"[A-HJ-NPR-Z0-9]{17}")
_FRAME_NUMBER = re.compile(r"([A-Z0-9]{3,10})-([A-Z0-9]{6,7})")
_SERIAL_LENGTH = 7
_CANDIDATE_LIMIT = 100
FITMENT_SCOPE = (
    "Production month, EPC source group, KPT/KIG characteristic rules and KRK frame ranges. "
    "Additional EPC notes remain visible."
)
_VARIANTS = (
    "SELECT v.*, c.code AS catalog_code, c.local_code, c.region, c.name AS catalog_name "
    "FROM variants v JOIN catalogs c ON c.id = v.catalog_id"
)


def resolve_vehicle(
    db: sqlite3.Connection, native: NativeCatalog, identifier: str, region: str | None = None
) -> Record:
    identifier = identifier.upper().replace(" ", "")
    region_filter = " AND c.region = ?" if region else ""
    region_args = [region] if region else []

    if VIN.fullmatch(identifier):
        lookup_type = "vin"
        variants = _variants(
            db,
            f" WHERE v.vin_prefix IN (?, ?){region_filter}",
            [identifier[:8], identifier[:9], *region_args],
        )
        frames = dict.fromkeys(variant["frame"] for variant in variants)
        vehicles = [
            vehicle
            for frame in frames
            if (vehicle := native.vehicle_block(VehicleBlocks.OVERSEAS, frame, identifier[-_SERIAL_LENGTH:]))
        ]
    else:
        match = _FRAME_NUMBER.fullmatch(identifier)
        if not match:
            raise InvalidRequestError("Use a 17-character VIN or FRAME-1234567")
        lookup_type = "frame"
        frame, serial = match[1], match[2].zfill(_SERIAL_LENGTH)
        vehicles = [
            vehicle
            for domain in (VehicleBlocks.DOMESTIC, VehicleBlocks.OVERSEAS)
            if (vehicle := native.vehicle_block(domain, frame, serial))
        ]
        variants = [
            variant
            for vehicle in vehicles
            for variant in _variants(
                db,
                f" WHERE v.frame = ? AND v.model = ?{region_filter}",
                [frame, vehicle["model"], *region_args],
            )
        ]
        if not variants:
            variants = _variants(
                db, f" WHERE v.frame = ?{region_filter} LIMIT {_CANDIDATE_LIMIT}", [frame, *region_args]
            )

    matches = _exact_matches(vehicles, variants)
    for found in matches:
        found["specifications"] = native.specifications(found["vehicle"], found["region"])
        found["characteristics"] = native.variant_characteristics(
            found["source_path"], found["source_offset"]
        )
    candidates = _distinct_models(variants)

    if matches:
        resolution = "exact"
    elif candidates:
        resolution = "catalog_candidates"
    else:
        resolution = "not_found"
    return {
        "identifier": identifier,
        "lookup_type": lookup_type,
        "resolution": resolution,
        "vehicles": vehicles,
        "matches": matches,
        "candidates": candidates[:_CANDIDATE_LIMIT],
        "fitment_scope": FITMENT_SCOPE,
    }


def exact_matches(
    db: sqlite3.Connection, native: NativeCatalog, identifier: str, region: str | None = None
) -> list[Record]:
    matches: list[Record] = resolve_vehicle(db, native, identifier, region)["matches"]
    if not matches:
        raise InvalidRequestError("Exact vehicle record not found; select a catalog from /vehicles/resolve")
    return matches


def _variants(db: sqlite3.Connection, condition: str, args: list[Any]) -> list[Record]:
    return [dict(row) for row in db.execute(_VARIANTS + condition, args)]


def _exact_matches(vehicles: list[Record], variants: list[Record]) -> list[Record]:
    unique: dict[tuple[Any, ...], Record] = {}
    for vehicle in vehicles:
        group = vehicle.get("specification_group")
        for variant in variants:
            if (
                variant["model"] == vehicle["model"]
                and (not group or variant["source_group"] == group)
                and in_production(variant, vehicle["production_month"])
            ):
                key = (
                    variant["catalog_id"],
                    variant["model"],
                    variant["source_group"],
                    variant["variant_code"],
                )
                unique[key] = {**variant, "vehicle": vehicle}
    return list(unique.values())


def _distinct_models(variants: list[Record]) -> list[Record]:
    seen: set[tuple[Any, Any]] = set()
    result = []
    for variant in variants:
        key = (variant["catalog_id"], variant["model"])
        if key not in seen:
            seen.add(key)
            result.append(variant)
    return result
