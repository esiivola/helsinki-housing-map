from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


WFS_URL = "https://kartta.hel.fi/ws/geoserver/avoindata/wfs"
LAYER = "avoindata:Toimipisterekisteri_yksikot"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the Service Map education snapshot.")
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    query = urlencode({"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": LAYER, "outputFormat": "application/json", "srsName": "EPSG:4326"})
    with urlopen(f"{WFS_URL}?{query}", timeout=120) as response:
        payload = response.read()
    temporary = arguments.output.with_suffix(f"{arguments.output.suffix}.partial")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(payload)
    temporary.replace(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
