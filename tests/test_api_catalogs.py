from pathlib import Path

from fastapi.testclient import TestClient

from epc.api import create_app


def test_health_and_stats(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok", "schema_version": "2"}
    stats = client.get("/api/v1/stats").json()
    assert stats["counts"]["parts"] == 2
    assert stats["regions"] == [{"region": "EU", "catalogs": 1, "applications": 2}]
    assert "source_root" not in stats


def test_catalog_search(client: TestClient) -> None:
    page = client.get("/api/v1/catalogs").json()
    assert [item["code"] for item in page["items"]] == ["EU:101510"]
    assert "hnb_path" not in page["items"][0]
    assert client.get("/api/v1/catalogs", params={"q": "test", "region": "EU"}).json()["total"] == 1
    assert client.get("/api/v1/catalogs", params={"region": "JP"}).json()["total"] == 0


def test_catalog_search_treats_wildcards_literally(client: TestClient) -> None:
    assert client.get("/api/v1/catalogs", params={"q": "%"}).json()["total"] == 0
    assert client.get("/api/v1/catalogs", params={"q": "_"}).json()["total"] == 0


def test_catalog_detail_accepts_local_and_market_codes(client: TestClient) -> None:
    detail = client.get("/api/v1/catalogs/101510").json()
    assert detail["code"] == "EU:101510"
    assert detail["part_count"] == 2
    assert client.get("/api/v1/catalogs/EU:101510").json() == detail
    assert client.get("/api/v1/catalogs/EU:999999").status_code == 404


def test_variants_and_figures(client: TestClient) -> None:
    variants = client.get("/api/v1/catalogs/EU:101510/variants", params={"q": "1TE"}).json()
    assert [item["model"] for item in variants["items"]] == ["ABC10L-TEST"]
    assert client.get("/api/v1/catalogs/EU:101510/variants", params={"q": "%"}).json()["total"] == 0
    figures = client.get("/api/v1/catalogs/EU:101510/figures").json()
    assert figures["items"] == [
        {"code": "1502", "name": "OIL FILTER", "part_count": 1},
        {"code": "4705", "name": "FRONT DISC BRAKE", "part_count": 1},
    ]


def test_figure_images_validate_the_figure_code(client: TestClient) -> None:
    assert client.get("/api/v1/catalogs/EU:101510/figures/4705/images").json() == {"items": []}
    assert client.get("/api/v1/catalogs/EU:101510/figures/47/images").status_code == 422
    assert client.get("/api/v1/catalogs/EU:101510/images/bad.png").status_code == 422
    assert client.get("/api/v1/catalogs/EU:101510/diagrams/ABCDEFG.png").status_code == 404


def test_provenance_listings(client: TestClient) -> None:
    sources = client.get("/api/v1/sources", params={"limit": 2}).json()
    assert sources["total"] > 2
    assert sources["has_more"] is True
    assert sources["items"][0]["path"] == "EU/SHAMEI.ACD"
    assert client.get("/api/v1/import-issues").json()["total"] == 0


def test_missing_index_is_reported_as_unavailable(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "absent.sqlite", tmp_path)) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        assert "python -m epc.importer" in response.json()["detail"]
        assert client.get("/").status_code == 200
    assert not (tmp_path / "absent.sqlite").exists()


def test_openapi_describes_every_json_response(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    for path, operations in schema["paths"].items():
        response = operations["get"]["responses"]["200"]["content"]
        if "application/json" in response:
            assert response["application/json"]["schema"], path


def test_web_interface_is_served(client: TestClient) -> None:
    assert "Toyota EPC" in client.get("/").text
    assert client.get("/static/js/main.js").status_code == 200
