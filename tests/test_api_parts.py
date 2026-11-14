import pytest
from fastapi.testclient import TestClient


def numbers(page: dict[str, list[dict[str, str]]]) -> list[str]:
    return [item["number"] for item in page["items"]]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("04465-0H", ["044650H020"]),
        ("044650h020", ["044650H020"]),
        ("brake pad", ["044650H020"]),
        ("oil fil", ["909150YZZE"]),
        ("missingword", []),
        ("", ["044650H020", "909150YZZE"]),
    ],
)
def test_search_by_number_and_name(client: TestClient, query: str, expected: list[str]) -> None:
    assert numbers(client.get("/api/v1/parts", params={"q": query}).json()) == expected


def test_search_result_shape(client: TestClient) -> None:
    page = client.get("/api/v1/parts", params={"q": "04465"}).json()
    assert page["items"] == [
        {
            "number": "044650H020",
            "display_number": "04465-0H020",
            "name": "PAD KIT, DISC BRAKE, FRONT",
            "catalog_count": 1,
        }
    ]
    assert page["total_is_estimate"] is False


def test_catalog_and_figure_filters(client: TestClient) -> None:
    page = client.get("/api/v1/parts", params={"catalog_code": "EU:101510", "figure_code": "4705"}).json()
    assert numbers(page) == ["044650H020"]
    assert client.get("/api/v1/parts", params={"region": "JP"}).json()["total"] == 0
    assert client.get("/api/v1/parts", params={"pnc": "90915"}).json()["total"] == 1
    assert client.get("/api/v1/parts", params={"figure_code": "4705"}).status_code == 422


def test_model_and_engine_filters(client: TestClient) -> None:
    assert client.get("/api/v1/parts", params={"engine": "1TEST"}).json()["total"] == 2
    assert client.get("/api/v1/parts", params={"model": "XYZ"}).json()["total"] == 0
    assert client.get("/api/v1/parts", params={"model": "_"}).json()["total"] == 0


def test_production_month_filter(client: TestClient) -> None:
    page = client.get("/api/v1/parts", params={"production_month": "2010-01"}).json()
    assert numbers(page) == ["044650H020"]
    assert page["total_is_estimate"] is True


def test_pagination_continues_from_next_offset(client: TestClient) -> None:
    first = client.get("/api/v1/parts", params={"limit": 1}).json()
    second = client.get("/api/v1/parts", params={"limit": 1, "offset": first["next_offset"]}).json()
    assert first["has_more"] is True
    assert second["has_more"] is False
    assert numbers(first) + numbers(second) == ["044650H020", "909150YZZE"]


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "offset=-1", "limit=abc", "production_month=2020-13"]
)
def test_invalid_parameters(client: TestClient, query: str) -> None:
    assert client.get("/api/v1/parts?" + query).status_code == 422


@pytest.mark.parametrize("query", ['" OR *', "'; DROP TABLE parts;--", "%", '"', "___"])
def test_search_syntax_is_literal(client: TestClient, query: str) -> None:
    assert client.get("/api/v1/parts", params={"q": query}).status_code == 200
    assert client.get("/api/v1/stats").json()["counts"]["parts"] == 2


def test_part_detail(client: TestClient) -> None:
    detail = client.get("/api/v1/parts/04465-0H020").json()
    assert detail["number"] == "044650H020"
    assert detail["names"] == [{"pnc": "04465", "name": "PAD KIT, DISC BRAKE, FRONT"}]
    assert [catalog["code"] for catalog in detail["catalogs"]] == ["EU:101510"]
    assert detail["list_price"] is None
    assert detail["related_numbers"] == []
    assert client.get("/api/v1/parts/9999999999").status_code == 404
    assert client.get("/api/v1/parts/wrong").status_code == 422


def test_applications_with_conditions(client: TestClient) -> None:
    path = "/api/v1/parts/044650H020/applications"
    assert client.get(path, params={"production_month": "2008-11"}).json()["total"] == 0
    assert client.get(path, params={"production_month": "2026-01"}).json()["total"] == 1
    entry = client.get(path).json()["items"][0]
    assert entry["quantity"] == "02"
    assert entry["catalog_name"] == "TEST CAR"
    assert [text["text"] for text in entry["texts"]] == ["ABC10..GRADE-A", "MARK TEST"]


def test_application_source_record(client: TestClient) -> None:
    identifier = client.get("/api/v1/parts/909150YZZE/applications").json()["items"][0]["id"]
    source = client.get(f"/api/v1/applications/{identifier}").json()
    assert source["source_path"] == "EU/101510/HNB10151.ACD"
    assert source["source_offset"] == 366
    assert source["record_size"] == 122
    assert source["xor_mask"] == 200
    assert len(source["raw_record"].encode("cp932")) == 122
    assert client.get("/api/v1/applications/EU:101510:367").status_code == 404
    assert client.get("/api/v1/applications/EU:101510:99999").status_code == 404
    assert client.get("/api/v1/applications/bad").status_code == 422
