from typing import Any

from epc.native import NativeCatalog

Record = dict[str, Any]

_ANY_SOURCE_GROUP = frozenset({"", "ZZZZ"})


def in_production(record: Record, production_month: str | None) -> bool:
    if not production_month:
        return True
    started, ended = record["production_from"], record["production_to"]
    return not (started and started > production_month) and not (ended and ended < production_month)


def fits(
    native: NativeCatalog,
    application: Record,
    variant: Record | None,
    production_month: str | None = None,
) -> bool:
    if not in_production(application, production_month):
        return False
    if not variant:
        return True
    if application["source_group"] not in {*_ANY_SOURCE_GROUP, variant["source_group"]}:
        return False
    return _matches_characteristics(native, application, variant) and _matches_frame_range(
        native, application, variant
    )


def _matches_characteristics(native: NativeCatalog, application: Record, variant: Record) -> bool:
    group = application["applicability_group"]
    if not group:
        return True
    region, code = variant["region"], variant["local_code"]
    legend = native.characteristic_legend(region, code)
    required: dict[str, set[str]] = {}
    for member in native.group_members(region, code, group):
        if member in legend:
            category, value = legend[member]
            required.setdefault(category, set()).add(value)
    actual = native.variant_characteristics(variant["source_path"], variant["source_offset"])
    return all(actual.get(category) in allowed for category, allowed in required.items())


def _matches_frame_range(native: NativeCatalog, application: Record, variant: Record) -> bool:
    group = application["frame_range_group"]
    vehicle = variant.get("vehicle")
    if not group or not vehicle:
        return True
    ranges = native.frame_ranges(variant["region"], variant["local_code"], group)
    return not ranges or any(
        start_frame == vehicle["frame"] == end_frame and start <= vehicle["serial"] <= end
        for start_frame, start, end_frame, end in ranges
    )
