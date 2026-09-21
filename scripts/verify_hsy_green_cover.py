from __future__ import annotations

from pathlib import Path

import pyogrio


paths = [
    Path("data/raw/hsy_maanpeite_muu_avoin_matala_kasvillisuus_2024.geojson"),
    Path("data/raw/hsy_maanpeite_puusto_2_10m_2024.geojson"),
    Path("data/raw/hsy_maanpeite_puusto_10_15m_2024.geojson"),
    Path("data/raw/hsy_maanpeite_puusto_15_20m_2024.geojson"),
    Path("data/raw/hsy_maanpeite_puusto_yli20m_2024.geojson"),
]

failed = False
for path in paths:
    try:
        info = pyogrio.read_info(path)
        print(f"OK {path.name}: {info['features']} features")
    except Exception as error:
        failed = True
        print(f"BROKEN {path.name}: {error}")

raise SystemExit(1 if failed else 0)
