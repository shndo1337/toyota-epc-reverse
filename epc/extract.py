import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

from epc.layout import REGIONS, Catalogs

INSTALLER = "Toyota_EPC_Setup_2025_01.exe"
INSTALLER_PARTS = re.compile(r"Toyota_EPC_Setup_2025_01(?:-\d+\.bin|\.exe)")
INSTALLER_PART_COUNT = 6
DATA_FOLDER = "app/epcdata"
LOCAL_INNOEXTRACT = Path("tools/inno-build/innoextract")


def extract(iso: Path, output: Path, innoextract: str | None = None) -> Path:
    if not iso.is_file():
        raise ValueError(f"ISO not found: {iso}")
    sevenzip = shutil.which("7z") or shutil.which("7zz")
    extractor = innoextract or _default_innoextract()
    if not sevenzip or not extractor:
        raise ValueError("7z and a recent innoextract are required; see scripts/build_innoextract.sh")

    installer = output.parent / "installer"
    installer.mkdir(parents=True, exist_ok=True)
    expected = _installer_parts(sevenzip, iso)
    if not all(_has_size(installer / name, size) for name, size in expected.items()):
        subprocess.run([sevenzip, "x", "-y", str(iso.resolve()), f"-o{installer.resolve()}"], check=True)

    subprocess.run(
        [
            extractor,
            "--silent",
            "--no-extract-unknown",
            "--include",
            DATA_FOLDER,
            "--output-dir",
            str(output.resolve()),
            str((installer / INSTALLER).resolve()),
        ],
        check=True,
    )
    data = output / DATA_FOLDER
    missing = [region for region in REGIONS if not (data / region / Catalogs.FILE).is_file()]
    if missing:
        raise ValueError(f"Extractor did not produce catalogs for: {', '.join(missing)}")
    return data


def _default_innoextract() -> str | None:
    return str(LOCAL_INNOEXTRACT) if LOCAL_INNOEXTRACT.is_file() else shutil.which("innoextract")


def _installer_parts(sevenzip: str, iso: Path) -> dict[str, int]:
    listing = subprocess.run(
        [sevenzip, "l", "-slt", str(iso.resolve())], check=True, capture_output=True, text=True
    ).stdout
    parts = {}
    for block in listing.split("\n\n"):
        fields = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
        name = fields.get("Path", "")
        if INSTALLER_PARTS.fullmatch(name):
            parts[name] = int(fields["Size"])
    if len(parts) != INSTALLER_PART_COUNT:
        raise ValueError(f"Expected {INSTALLER_PART_COUNT} installer files in {iso.name}")
    return parts


def _has_size(path: Path, size: int) -> bool:
    return path.is_file() and path.stat().st_size == size


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract EPC data from the Toyota EPC ISO without running the installer."
    )
    parser.add_argument("--iso", type=Path, default=Path("Toyota_EPC_2025_01.iso"))
    parser.add_argument("--output", type=Path, default=Path("data/full"))
    parser.add_argument("--innoextract", default=os.environ.get("INNOEXTRACT"))
    args = parser.parse_args()
    try:
        data = extract(args.iso, args.output, args.innoextract)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Extraction failed: {error}\n")
    print(f"Extracted EPC data to {data}")


if __name__ == "__main__":
    main()
