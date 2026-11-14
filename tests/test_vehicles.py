import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from epc.native import NativeCatalog
from epc.services.fitment import fits
from epc.services.vehicles import resolve_vehicle
from tests.samples import TEST_FRAME, TEST_VIN


def test_vin_resolves_to_the_native_vehicle_record(client: TestClient) -> None:
    result = client.get(f"/api/v1/vin/{TEST_VIN}").json()
    assert result["resolution"] == "exact"
    assert result["lookup_type"] == "vin"
    match = result["matches"][0]
    vehicle = match["vehicle"]
    assert vehicle["model"] == "ABC10L-TEST"
    assert vehicle["production_month"] == "2008-12"
    assert vehicle["color"] == "040"
    assert vehicle["trim"] == "FA10"
    assert match["specifications"][0]["value"] == "AB"
    assert match["characteristics"]["01"] == "1TEST"


def test_frame_number_lookup(client: TestClient) -> None:
    result = client.get("/api/v1/vehicles/resolve", params={"identifier": TEST_FRAME}).json()
    assert result["lookup_type"] == "frame"
    assert result["vehicles"][0]["frame_number"] == TEST_FRAME


def test_unknown_serial_is_not_an_exact_decode(client: TestClient) -> None:
    result = client.get(f"/api/v1/vin/{TEST_VIN[:-3]}999").json()
    assert result["resolution"] == "catalog_candidates"
    assert result["matches"] == []
    assert [candidate["model"] for candidate in result["candidates"]] == ["ABC10L-TEST"]


def test_invalid_identifiers(client: TestClient) -> None:
    assert client.get("/api/v1/vin/invalid").status_code == 422
    assert client.get("/api/v1/vehicles/resolve", params={"identifier": "NOT A FRAME"}).status_code == 422
    unknown = client.get("/api/v1/vehicles/resolve", params={"identifier": "XYZ99-1234567"}).json()
    assert unknown["resolution"] == "not_found"


def test_vehicle_filter_checks_characteristics_not_variant_numbers(client: TestClient) -> None:
    result = client.get("/api/v1/parts", params={"q": "oil filter", "vehicle": TEST_VIN}).json()
    assert [item["number"] for item in result["items"]] == ["909150YZZE"]
    assert result["total_is_estimate"] is True


def test_vehicle_filter_requires_an_exact_record(client: TestClient) -> None:
    response = client.get("/api/v1/parts", params={"vehicle": TEST_VIN[:-3] + "999"})
    assert response.status_code == 422


def test_figure_images_use_the_vehicle_production_month(client: TestClient) -> None:
    response = client.get("/api/v1/catalogs/EU:101510/figures/1502/images", params={"vehicle": TEST_VIN})
    assert response.json() == {"items": []}


def test_fitment_rules(database: Path, epc_root: Path) -> None:
    native = NativeCatalog(epc_root)
    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row
        variant = resolve_vehicle(db, native, TEST_VIN)["matches"][0]
    application = native.applications("EU", "101510", "90915")[0]

    assert fits(native, application, variant, "2008-12")
    assert not fits(native, application, variant, "2009-01")
    assert fits(native, application, None, "2008-12")

    outside_range = {**variant, "vehicle": {**variant["vehicle"], "serial": "0000100"}}
    assert not fits(native, application, outside_range, "2008-12")

    other_group = {**variant, "source_group": "9999"}
    assert not fits(native, application, other_group, "2008-12")

    (epc_root / "EU" / "101510" / "KIG10151.D01").write_bytes(b"01WRONG".ljust(82))
    native.clear_caches()
    assert not fits(native, application, variant, "2008-12")


def test_accessories(client: TestClient) -> None:
    result = client.get("/api/v1/accessories", params={"q": "floor mat"}).json()
    assert result["total"] == 1
    summary = result["items"][0]
    assert summary["display_number"] == "PZ31042032C0"
    detail = client.get(f"/api/v1/accessories/{summary['accessory_id']}").json()
    assert detail["model_codes"] == "ABC10L-TEST"
    assert detail["image_url"] is None
    assert client.get("/api/v1/accessories", params={"vehicle": TEST_VIN}).json()["total"] == 1
    assert client.get("/api/v1/accessories", params={"catalog_code": "EU:101510"}).json()["total"] == 1
    assert client.get("/api/v1/accessories", params={"production_month": "2000-01"}).json()["total"] == 0
    assert client.get("/api/v1/accessories", params={"q": "PZ310"}).json()["total"] == 1
    assert client.get(f"/api/v1/accessories/{summary['accessory_id']}/image").status_code == 404
    assert client.get("/api/v1/accessories/999").status_code == 404
