from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool


class ContinuationPage(Page[T], Generic[T]):
    next_offset: int


class ScanPage(ContinuationPage[T], Generic[T]):
    total_is_estimate: bool


class Health(BaseModel):
    status: str
    schema_version: str


class RegionStats(BaseModel):
    region: str
    catalogs: int
    applications: int


class Stats(BaseModel):
    schema_version: str
    dataset: str
    region: str
    scope: str
    imported_at: str
    build_seconds: str
    counts: dict[str, int]
    regions: list[RegionStats]


class SourceFile(BaseModel):
    id: int
    path: str
    sha256: str
    size_bytes: int
    record_size: int
    xor_mask: int


class ImportIssue(BaseModel):
    source_path: str
    source_offset: int | None
    reason: str
    raw_hex: str | None


class Catalog(BaseModel):
    id: int
    code: str
    local_code: str
    region: str
    name: str
    model_codes: str
    production_from: str | None
    production_to: str | None
    revision: str | None
    imported: bool
    application_count: int
    record_count: int


class CatalogDetail(Catalog):
    part_count: int


class Variant(BaseModel):
    id: int
    catalog_id: int
    vin_prefix: str
    model: str
    frame: str
    source_group: str
    variant_code: str
    production_from: str | None
    production_to: str | None
    engine: str
    attributes: str
    source_path: str
    source_offset: int


class Figure(BaseModel):
    code: str
    name: str | None
    part_count: int


class FigureImage(BaseModel):
    image: str
    sequence: str
    production_from: str | None
    production_to: str | None
    source_offset: int
    thumbnail_url: str
    diagram_url: str


class FigureImages(BaseModel):
    items: list[FigureImage]


class Vehicle(BaseModel):
    frame: str
    serial: str
    frame_number: str
    model: str
    production_month: str
    color: str
    trim: str
    specification_group: str
    specification_code: str
    source_path: str
    source_offset: int
    source_sha256: str
    raw_hex: str
    record_size: int


class VehicleCandidate(Variant):
    catalog_code: str
    local_code: str
    region: str
    catalog_name: str


class Specification(BaseModel):
    category: str
    value: str
    source_path: str
    source_offset: int


class VehicleMatch(VehicleCandidate):
    vehicle: Vehicle
    specifications: list[Specification]
    characteristics: dict[str, str]


class VehicleResolution(BaseModel):
    identifier: str
    lookup_type: str
    resolution: str
    vehicles: list[Vehicle]
    matches: list[VehicleMatch]
    candidates: list[VehicleCandidate]
    fitment_scope: str


class PartSummary(BaseModel):
    number: str
    display_number: str
    name: str | None
    catalog_count: int


class PartName(BaseModel):
    pnc: str
    name: str | None


class Price(BaseModel):
    amount: int | None
    currency: str
    source_path: str
    source_offset: int
    raw_value: str
    dataset: str


class RelatedNumber(BaseModel):
    region: str
    number: str
    source_type: str
    source_path: str
    source_offset: int
    raw_record: str


class PartDetail(BaseModel):
    number: str
    names: list[PartName]
    catalogs: list[Catalog]
    list_price: Price | None
    related_numbers: list[RelatedNumber]


class SourceText(BaseModel):
    kind: str
    sequence: str
    text: str
    source_offset: int


class ApplicationRecord(BaseModel):
    id: str
    catalog_code: str
    part_number: str
    pnc: str
    source_group: str
    quantity: str
    production_from: str | None
    production_to: str | None
    source_path: str
    source_offset: int
    raw_record: str
    applicability_group: str
    frame_range_group: str
    texts: list[SourceText]


class Application(ApplicationRecord):
    catalog_name: str
    name: str | None


class ApplicationSource(ApplicationRecord):
    source_sha256: str
    record_size: int
    xor_mask: int


class AccessorySummary(BaseModel):
    accessory_id: int
    number: str
    display_number: str
    name: str
    title: str
    model_codes: str
    catalog_count: int


class Accessory(BaseModel):
    id: int
    group_code: str
    document: str
    title: str
    production_from: str | None
    production_to: str | None
    name: str
    number: str
    destination: str
    quantity: str
    notes: str
    model_codes: str
    image: str
    image_url: str | None
    source_path: str
    source_row: int
    raw_fields: list[str]
