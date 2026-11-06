"""Download the original UCI workbook without modifying or replacing it."""

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
WORKBOOK = RAW / "Online Retail.xlsx"
MANIFEST = RAW / "source_manifest.json"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    if WORKBOOK.exists():
        if not MANIFEST.exists():
            raise SystemExit("Workbook exists without a source manifest; verify its source before using it.")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if sha256(WORKBOOK.read_bytes()).hexdigest() != manifest["sha256"]:
            raise SystemExit("Workbook checksum differs from the recorded source; investigate before proceeding.")
        print(f"Using existing, checksum-verified file: {WORKBOOK}")
        return

    local_archive = RAW / "online_retail.zip"
    if local_archive.exists():
        print("Reading the locally downloaded UCI archive...")
        archive_bytes = local_archive.read_bytes()
    else:
        print("Downloading the original UCI archive...")
        with urlopen(URL, timeout=120) as response:
            archive_bytes = response.read()
    with ZipFile(BytesIO(archive_bytes)) as archive:
        matches = [name for name in archive.namelist() if Path(name).name == WORKBOOK.name]
        if len(matches) != 1:
            raise RuntimeError("Expected exactly one Online Retail.xlsx in the UCI archive.")
        workbook_bytes = archive.read(matches[0])
    # Write only the expected workbook; never extract arbitrary archive paths.
    WORKBOOK.write_bytes(workbook_bytes)
    manifest = {
        "source_page": "https://archive.ics.uci.edu/dataset/352/online+retail",
        "download_url": URL,
        "ingestion_method": "local UCI archive" if local_archive.exists() else "direct HTTPS download",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "file": WORKBOOK.name,
        "bytes": len(workbook_bytes),
        "sha256": sha256(workbook_bytes).hexdigest(),
        "archive_sha256": sha256(archive_bytes).hexdigest(),
        "citation": "Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33.",
        "license": "CC BY 4.0",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {WORKBOOK} ({len(workbook_bytes):,} bytes)")


if __name__ == "__main__":
    main()
