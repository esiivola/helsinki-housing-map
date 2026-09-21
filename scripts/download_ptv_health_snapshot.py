from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).parents[1]))

from pipeline.sources.ptv import WELLBEING_SERVICE_CLASS_GROUPS, classify_wellbeing_location, classify_wellbeing_service_classes


BASE_URL = "https://api-gw.palvelutietovaranto.suomi.fi/api/v12"
METRO_BOUNDS = (24.3, 59.8, 25.5, 60.5)
METRO_MUNICIPALITIES = ("049", "091", "092", "235")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download classified PTV healthcare service locations.")
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    key = os.environ.get("PTV_API_KEY")
    if not key:
        parser.error("PTV_API_KEY is required")
    organizations = {item["contentId"]: item for item in _pages("organization/search", key)}
    services = _wellbeing_services(key)
    transformer = Transformer.from_crs(3067, 4326, always_xy=True)
    locations = []
    for channel in _pages("service-channel/search", key, {
        "channelTypes": "ServiceLocation", "areaType": "LimitedArea",
        "municipalities": list(METRO_MUNICIPALITIES), "municipalitiesMatch": "any",
    }):
        organization = organizations.get(channel.get("organizationContentId"))
        coordinate = _coordinate(channel)
        if organization is None or coordinate is None:
            continue
        longitude, latitude = transformer.transform(*coordinate)
        if not METRO_BOUNDS[0] <= longitude <= METRO_BOUNDS[2] or not METRO_BOUNDS[1] <= latitude <= METRO_BOUNDS[3]:
            continue
        locations.append((channel, organization, longitude, latitude))
    service_groups = _service_groups_by_channel(services, key)
    features = [
        {"type": "Feature", "properties": {"health_group": group, "name": _finnish_name(channel) or _finnish_name(organization)}, "geometry": {"type": "Point", "coordinates": [longitude, latitude]}}
        for channel, organization, longitude, latitude in locations
        for group in sorted(classify_wellbeing_location(organization, channel, service_groups.get(channel["contentId"], ())))
    ]
    temporary = arguments.output.with_suffix(f"{arguments.output.suffix}.partial")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")))
    temporary.replace(arguments.output)
    return 0


def _pages(endpoint: str, key: str, extra: dict[str, str | list[str]] | None = None):
    page = 1
    while True:
        query = {"page": str(page), "pageSize": "100", **(extra or {})}
        request = Request(f"{BASE_URL}/{endpoint}?{urlencode(query, doseq=True)}", headers={"x-api-key": key})
        with urlopen(request, timeout=120) as response:
            payload = json.load(response)
        yield from payload["items"]
        if page >= payload["totalPages"]:
            return
        page += 1


def _wellbeing_services(key: str) -> dict[str, set[str]]:
    services: dict[str, set[str]] = {}
    for codes in WELLBEING_SERVICE_CLASS_GROUPS.values():
        for service in _pages("service/search", key, {"serviceClasses": list(codes), "serviceClassesMatch": "any"}):
            content_id = service.get("contentId")
            classes = service.get("serviceClasses")
            if isinstance(content_id, str) and isinstance(classes, list):
                groups = classify_wellbeing_service_classes(tuple(code for code in classes if isinstance(code, str)))
                if groups:
                    services.setdefault(content_id, set()).update(groups)
    return services


def _service_groups_by_channel(services: dict[str, set[str]], key: str) -> dict[str, tuple[str, ...]]:
    groups: dict[str, set[str]] = {}
    service_ids = list(services)
    for start in range(0, len(service_ids), 20):
        for connection in _pages("connection/search", key, {"serviceContentIds": service_ids[start:start + 20]}):
            channel_id = connection.get("channelContentId")
            service_id = connection.get("serviceContentId")
            if isinstance(channel_id, str) and isinstance(service_id, str) and service_id in services:
                groups.setdefault(channel_id, set()).update(services[service_id])
    return {channel_id: tuple(sorted(values)) for channel_id, values in groups.items()}


def _coordinate(channel: dict[str, object]) -> tuple[float, float] | None:
    location = channel.get("location")
    if not isinstance(location, dict):
        return None
    for address in location.get("streetAddresses", []):
        if not isinstance(address, dict):
            continue
        for coordinate in address.get("coordinates", []):
            if isinstance(coordinate, dict) and coordinate.get("system") == "EPSG:3067":
                return float(coordinate["easting"]), float(coordinate["northing"])
    return None


def _finnish_name(item: dict[str, object]) -> str:
    versions = item.get("languageVersions")
    finnish = versions.get("fi") if isinstance(versions, dict) else None
    return str(finnish.get("name", "")) if isinstance(finnish, dict) else ""


if __name__ == "__main__":
    raise SystemExit(main())
