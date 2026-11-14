import re
import sqlite3

from epc.errors import InvalidRequestError, NotFoundError
from epc.native import NativeCatalog
from epc.services.catalogs import Record, get_catalog
from epc.services.fitment import in_production
from epc.services.vehicles import resolve_vehicle

_FIGURE = re.compile(r"\d{4}")
_IMAGE = re.compile(r"[A-Z0-9]{6,7}")


def figure_images(
    db: sqlite3.Connection,
    native: NativeCatalog,
    code: str,
    figure: str,
    *,
    production_month: str | None,
    vehicle: str | None,
) -> list[Record]:
    catalog = get_catalog(db, code)
    if not _FIGURE.fullmatch(figure):
        raise InvalidRequestError("Expected a four-digit figure code")
    images = native.figure_images(catalog["region"], catalog["local_code"], figure)
    if vehicle and not production_month:
        matches = resolve_vehicle(db, native, vehicle, catalog["region"])["matches"]
        production_month = next(
            (
                match["vehicle"]["production_month"]
                for match in matches
                if match["catalog_code"] == catalog["code"]
            ),
            None,
        )
    images = [image for image in images if in_production(image, production_month)]
    for image in images:
        image["thumbnail_url"] = f"/api/v1/catalogs/{catalog['code']}/images/{image['image']}.png"
        image["diagram_url"] = f"/api/v1/catalogs/{catalog['code']}/diagrams/{image['image']}.png"
    return images


def thumbnail(db: sqlite3.Connection, native: NativeCatalog, code: str, image: str) -> bytes:
    catalog = get_catalog(db, code)
    _check_image(image)
    data = native.thumbnail(catalog["region"], catalog["local_code"], image)
    if not data:
        raise NotFoundError("Thumbnail not available")
    return data


def diagram(db: sqlite3.Connection, native: NativeCatalog, code: str, image: str) -> bytes:
    catalog = get_catalog(db, code)
    _check_image(image)
    try:
        data = native.diagram(catalog["region"], image)
    except (ValueError, OSError) as error:
        raise InvalidRequestError("This illustration encoding is not supported") from error
    if not data:
        raise NotFoundError("Diagram not available")
    return data


def _check_image(image: str) -> None:
    if not _IMAGE.fullmatch(image):
        raise InvalidRequestError("Invalid image identifier")
