from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.build import build_fixture_release, build_hsy_release
from pipeline.verify_release import verify_release
from pipeline.models import SourceManifest


PAAVO_SNAPSHOT = Path("data/raw/paavo_2026.geojson")
HELSINKI_NOISE_SNAPSHOT = Path("data/raw/helsinki_noise_2022_day_upper.geojson")
HELSINKI_NIGHT_NOISE_SNAPSHOT = Path("data/raw/helsinki_noise_2022_night_upper.geojson")
HELSINKI_ACTIVE_PLANS_SNAPSHOT = Path("data/raw/helsinki_active_plans_2026-08-30.geojson")
VANTAA_PROPERTY_SNAPSHOT = Path("data/raw/vantaa_property_map_2026.geojson")
OSM_SNAPSHOT = Path("data/raw/hsl_osm_2026-08-25.pbf")
GTFS_SNAPSHOT = Path("data/raw/hsl_gtfs_2026-08-27.zip")
WORKPLACE_TRANSIT_BATCHES = Path("data/work/transit-workplace-morning-batches")
HELSINKI_CYCLE_NETWORK_SNAPSHOT = Path("data/raw/helsinki_cycle_network_2026-08-31.geojson")
HSY_GREEN_COVER_SNAPSHOTS = tuple(Path("data/raw") / name for name in (
    "hsy_maanpeite_muu_avoin_matala_kasvillisuus_2024.geojson", "hsy_maanpeite_puusto_2_10m_2024.geojson", "hsy_maanpeite_puusto_10_15m_2024.geojson", "hsy_maanpeite_puusto_15_20m_2024.geojson", "hsy_maanpeite_puusto_yli20m_2024.geojson",
))


def _optional_source_manifest(parser, snapshot: Path | None, provenance: tuple[str | None, str | None, str | None], flag: str, name: str, source_id: str, source_url: str, attribution: str, coverage: str, licence_id: str, licence_url: str, processing_method: str, caveats: tuple[str, ...], rationale: str) -> SourceManifest | None:
    if snapshot is None:
        if any(provenance):
            parser.error(f"{flag.removesuffix('-snapshot')} provenance requires {flag}")
        return None
    if not all(provenance):
        parser.error(f"{flag} requires retrieved-at, vintage, and checksum")
    retrieved_at, vintage, checksum = provenance
    return SourceManifest(source_id, name, source_url, licence_url, licence_id, attribution, retrieved_at, vintage, coverage, checksum, processing_method, caveats, "allowed", rationale)


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline")
    subcommands = parser.add_subparsers(dest="command", required=True)
    fixture_release = subcommands.add_parser("fixture-release")
    fixture_release.add_argument("fixture", type=Path)
    fixture_release.add_argument("output", type=Path)
    hsy_release = subcommands.add_parser("hsy-release")
    hsy_release.add_argument("snapshot", type=Path)
    hsy_release.add_argument("output", type=Path)
    hsy_release.add_argument("--retrieved-at", required=True)
    hsy_release.add_argument("--vintage", required=True)
    hsy_release.add_argument("--checksum", required=True)
    hsy_release.add_argument("--morning-transit-batches", type=Path)
    hsy_release.add_argument("--workplace-transit-batches", type=Path, default=WORKPLACE_TRANSIT_BATCHES)
    hsy_release.add_argument("--main-cycle-network-snapshot", type=Path)
    hsy_release.add_argument("--green-cover-snapshot", type=Path, action="append", default=[])
    hsy_release.add_argument("--green-cover-checkpoint-dir", type=Path, default=Path("data/work/green-cover-300m"))
    hsy_release.add_argument("--paavo-snapshot", type=Path, default=PAAVO_SNAPSHOT)
    hsy_release.add_argument("--noise-snapshot", type=Path, default=HELSINKI_NOISE_SNAPSHOT)
    hsy_release.add_argument("--night-noise-snapshot", type=Path, default=HELSINKI_NIGHT_NOISE_SNAPSHOT)
    hsy_release.add_argument("--active-plans-snapshot", type=Path, default=HELSINKI_ACTIVE_PLANS_SNAPSHOT)
    hsy_release.add_argument("--vantaa-property-snapshot", type=Path, default=VANTAA_PROPERTY_SNAPSHOT)
    hsy_release.add_argument("--espoo-city-land-snapshot", type=Path)
    hsy_release.add_argument("--espoo-city-land-retrieved-at")
    hsy_release.add_argument("--espoo-city-land-vintage")
    hsy_release.add_argument("--espoo-city-land-checksum")
    hsy_release.add_argument("--vantaa-buildings-snapshot", type=Path)
    hsy_release.add_argument("--vantaa-buildings-retrieved-at")
    hsy_release.add_argument("--vantaa-buildings-vintage")
    hsy_release.add_argument("--vantaa-buildings-checksum")
    hsy_release.add_argument("--osm-snapshot", type=Path, default=OSM_SNAPSHOT)
    hsy_release.add_argument("--helsinki-buildings-snapshot", type=Path)
    hsy_release.add_argument("--helsinki-buildings-retrieved-at")
    hsy_release.add_argument("--helsinki-buildings-vintage")
    hsy_release.add_argument("--helsinki-buildings-checksum")
    hsy_release.add_argument("--service-map-snapshot", type=Path)
    hsy_release.add_argument("--service-map-retrieved-at")
    hsy_release.add_argument("--service-map-vintage")
    hsy_release.add_argument("--service-map-checksum")
    hsy_release.add_argument("--ptv-health-snapshot", type=Path)
    hsy_release.add_argument("--ptv-health-retrieved-at")
    hsy_release.add_argument("--ptv-health-vintage")
    hsy_release.add_argument("--ptv-health-checksum")
    verify = subcommands.add_parser("verify-release")
    verify.add_argument("output", type=Path)
    arguments = parser.parse_args()

    if arguments.command == "fixture-release":
        build_fixture_release(arguments.fixture, arguments.output)
        return 0
    if arguments.command == "hsy-release":
        helsinki_buildings_source_manifest = None
        helsinki_buildings_provenance = (
            arguments.helsinki_buildings_retrieved_at,
            arguments.helsinki_buildings_vintage,
            arguments.helsinki_buildings_checksum,
        )
        if arguments.helsinki_buildings_snapshot is not None:
            if not all(helsinki_buildings_provenance):
                parser.error("--helsinki-buildings-snapshot requires retrieved-at, vintage, and checksum")
            helsinki_buildings_source_manifest = SourceManifest(
                source_id="helsinki_buildings",
                name="Helsinki buildings",
                source_url="https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
                licence_url="https://creativecommons.org/licenses/by/4.0/",
                licence_id="CC-BY-4.0",
                attribution="Helsingin kaupunki",
                retrieved_at=arguments.helsinki_buildings_retrieved_at,
                vintage=arguments.helsinki_buildings_vintage,
                coverage="Helsinki",
                checksum=arguments.helsinki_buildings_checksum,
                processing_method="VTJ-PRT join and Building Classification 2018 mapping",
                caveats=("Only classes 0110, 0111, 0112, 0120, and 0121 map to release-1 house types.",),
                redistribution_decision="allowed",
                rationale="The published dataset is CC BY 4.0.",
            )
        elif any(helsinki_buildings_provenance):
            parser.error("Helsinki buildings provenance requires --helsinki-buildings-snapshot")
        espoo_city_land_source_manifest = None
        espoo_city_land_provenance = (
            arguments.espoo_city_land_retrieved_at,
            arguments.espoo_city_land_vintage,
            arguments.espoo_city_land_checksum,
        )
        if arguments.espoo_city_land_snapshot is not None:
            if not all(espoo_city_land_provenance):
                parser.error("--espoo-city-land-snapshot requires retrieved-at, vintage, and checksum")
            espoo_city_land_source_manifest = SourceManifest(
                source_id="espoo_city_land", name="Espoo city land ownership",
                source_url="https://hri.fi/data/dataset/espoon-kaupungin-maanomistus",
                licence_url="https://creativecommons.org/licenses/by/4.0/", licence_id="CC-BY-4.0",
                attribution="Espoon kaupunki", retrieved_at=arguments.espoo_city_land_retrieved_at,
                vintage=arguments.espoo_city_land_vintage, coverage="Espoo",
                checksum=arguments.espoo_city_land_checksum,
                processing_method="Offline full-footprint city-land overlay",
                caveats=("Only full building-footprint coverage is classified as city ownership.",),
                redistribution_decision="allowed", rationale="The published dataset is CC BY 4.0.",
            )
        elif any(espoo_city_land_provenance):
            parser.error("Espoo city-land provenance requires --espoo-city-land-snapshot")
        vantaa_buildings_source_manifest = None
        vantaa_buildings_provenance = (arguments.vantaa_buildings_retrieved_at, arguments.vantaa_buildings_vintage, arguments.vantaa_buildings_checksum)
        if arguments.vantaa_buildings_snapshot is not None:
            if not all(vantaa_buildings_provenance):
                parser.error("--vantaa-buildings-snapshot requires retrieved-at, vintage, and checksum")
            vantaa_buildings_source_manifest = SourceManifest("vantaa_buildings", "Vantaa buildings", "https://gis.vantaa.fi/geoserver/wfs", "https://creativecommons.org/licenses/by/4.0/", "CC-BY-4.0", "Vantaan kaupunki", arguments.vantaa_buildings_retrieved_at, arguments.vantaa_buildings_vintage, "Vantaa", arguments.vantaa_buildings_checksum, "VTJ-PRT join and Building Classification 2018 mapping", ("Only mapped residential classes are published.",), "allowed", "The published dataset is CC BY 4.0.")
        elif any(vantaa_buildings_provenance):
            parser.error("Vantaa buildings provenance requires --vantaa-buildings-snapshot")
        service_map_source_manifest = _optional_source_manifest(
            parser, arguments.service_map_snapshot,
            (arguments.service_map_retrieved_at, arguments.service_map_vintage, arguments.service_map_checksum),
            "--service-map-snapshot", "Service Map education and daycare units", "service_map_education",
            "https://kartta.hel.fi/ws/geoserver/avoindata/wfs", "Helsingin kaupunki ja pääkaupunkiseudun kunnat", "Helsinki, Espoo, Vantaa, Kauniainen",
            "CC-BY-4.0", "https://creativecommons.org/licenses/by/4.0/", "Offline service-category filtering and pedestrian routing",
            ("Only published physical service units matching the documented service labels are included.",),
            "The Service Map source is published under CC BY 4.0.",
        )
        ptv_health_source_manifest = _optional_source_manifest(
            parser, arguments.ptv_health_snapshot,
            (arguments.ptv_health_retrieved_at, arguments.ptv_health_vintage, arguments.ptv_health_checksum),
            "--ptv-health-snapshot", "PTV wellbeing service locations", "ptv_healthcare",
            "https://api-gw.palvelutietovaranto.suomi.fi/api/v12", "Digi- ja väestötietovirasto", "Helsinki, Espoo, Vantaa, Kauniainen",
            "CC0-1.0", "https://creativecommons.org/publicdomain/zero/1.0/", "Offline physical-location filtering, PTV service-link classification, and transparent provider/name classification",
            ("Private-provider entries in PTV are voluntary and can be incomplete.", "Dental, neuvola, mental-health/substance-use, and social-service groups require an explicit linked PTV service class."),
            "PTV data is published under CC0.",
        )
        build_hsy_release(
            arguments.snapshot,
            arguments.output,
            SourceManifest(
                source_id="hsy_buildings",
                name="HSY metropolitan buildings",
                source_url="https://kartta.hsy.fi/geoserver/wfs",
                licence_url="https://creativecommons.org/licenses/by/4.0/",
                licence_id="CC-BY-4.0",
                attribution="Helsingin seudun ympäristöpalvelut HSY",
                retrieved_at=arguments.retrieved_at,
                vintage=arguments.vintage,
                coverage="Helsinki, Espoo, Vantaa, Kauniainen",
                checksum=arguments.checksum,
                processing_method="WFS download and direct normalization",
                caveats=(
                    "Older records may be uncertain.",
                    "Building-level house type is unavailable in this source snapshot.",
                ),
                redistribution_decision="allowed",
                rationale="The published dataset is CC BY 4.0.",
            ),
            paavo_snapshot=arguments.paavo_snapshot,
            paavo_source_manifest=SourceManifest(
                source_id="paavo_income",
                name="Statistics Finland Paavo postal-area income",
                source_url="https://geo.stat.fi/geoserver/postialue/wfs",
                licence_url="https://stat.fi/fi/palvelut/tilastodatapalvelut/paikkatietoaineistot/postinumeroalueittainen-paikkatieto-paavo",
                licence_id="open",
                attribution="Tilastokeskus, Paavo",
                retrieved_at="2026-08-27T07:30:27+03:00",
                vintage="2026",
                coverage="Finland",
                checksum="sha256:878437b3d6df277f8811728fc5bef31362ac1dabb906f435c7982aa4d9b11cfa",
                processing_method="Offline postal-area assignment with suppressed values normalized to unknown",
                caveats=(
                    "Postal-area income is contextual, not a building-level measurement.",
                    "Source value -1 is suppressed and becomes unknown.",
                ),
                redistribution_decision="allowed",
                rationale="Paavo is a free postal-area statistics dataset.",
            ),
            noise_snapshot=arguments.noise_snapshot,
            noise_source_manifest=SourceManifest(
                source_id="helsinki_noise_2022",
                name="Helsinki traffic noise zones",
                source_url="https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
                licence_url="https://creativecommons.org/licenses/by/4.0/",
                licence_id="CC-BY-4.0",
                attribution="Helsingin kaupunki",
                retrieved_at="2026-08-27T08:39:21+03:00",
                vintage="2022",
                coverage="Helsinki",
                checksum="sha256:0ac7a45e9321b278635719df1e801ad56e0d981527e6fc6bedd4c9ae66e3cc7a",
                processing_method="Offline maximum daytime noise-zone upper-bound aggregation",
                caveats=(
                    "Modeled zone upper bound, not a building-level maximum.",
                    "Only source-covered footprint share is known.",
                ),
                redistribution_decision="allowed",
                rationale="The published dataset is CC BY 4.0.",
            ),
            night_noise_snapshot=arguments.night_noise_snapshot,
            night_noise_source_manifest=SourceManifest(
                source_id="helsinki_noise_night_2022",
                name="Helsinki nighttime traffic noise zones",
                source_url="https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
                licence_url="https://creativecommons.org/licenses/by/4.0/",
                licence_id="CC-BY-4.0",
                attribution="Helsingin kaupunki",
                retrieved_at="2026-08-30T13:54:00+03:00",
                vintage="2022",
                coverage="Helsinki",
                checksum="sha256:df377a30beb1d0e6434827d44f6cc3a1301ec9a80ae7accbcc91cdfbe74c6079",
                processing_method="Offline maximum nighttime noise-zone upper-bound aggregation",
                caveats=(
                    "Modeled zone upper bound, not a building-level maximum.",
                    "Only source-covered footprint share is known.",
                ),
                redistribution_decision="allowed",
                rationale="The published dataset is CC BY 4.0.",
            ),
            active_plans_snapshot=arguments.active_plans_snapshot,
            active_plans_source_manifest=SourceManifest(
                source_id="helsinki_active_plans",
                name="Helsinki active detailed-plan areas",
                source_url="https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
                licence_url="https://creativecommons.org/licenses/by/4.0/",
                licence_id="CC-BY-4.0",
                attribution="Helsingin kaupunki",
                retrieved_at="2026-08-30T14:09:00+03:00",
                vintage="2026-08-28",
                coverage="Helsinki",
                checksum="sha256:28d9bf1fd5a4e22eeecd7ab38db9158c02129acad0a8cf8073d78010e1987791",
                processing_method="Offline building-footprint intersection with active detailed-plan areas",
                caveats=(
                    "An active planning area does not predict construction timing, scale, or disturbance.",
                    "Only Helsinki is covered.",
                ),
                redistribution_decision="allowed",
                rationale="The published dataset is CC BY 4.0.",
            ),
            espoo_city_land_snapshot=arguments.espoo_city_land_snapshot,
            espoo_city_land_source_manifest=espoo_city_land_source_manifest,
            vantaa_buildings_snapshot=arguments.vantaa_buildings_snapshot,
            vantaa_buildings_source_manifest=vantaa_buildings_source_manifest,
            vantaa_property_snapshot=arguments.vantaa_property_snapshot,
            vantaa_property_source_manifest=SourceManifest(
                source_id="vantaa_property_map", name="Vantaa property map",
                source_url="https://gis.vantaa.fi/geoserver/wfs",
                licence_url="https://creativecommons.org/licenses/by/4.0/", licence_id="CC-BY-4.0",
                attribution="Vantaan kaupunki", retrieved_at="2026-08-27T10:09:00+03:00",
                vintage="2026-08-27", coverage="Vantaa",
                checksum="sha256:9114c49ac203d97e70bd1779e87f9e1cde087635f760c50ab2073566c52d37fa",
                processing_method="Offline positive lease-area evidence overlay",
                caveats=("Only explicit vuokraalue polygons support leased tenure.",),
                redistribution_decision="allowed", rationale="The published dataset is CC BY 4.0.",
            ),
            osm_snapshot=arguments.osm_snapshot,
            osm_source_manifest=SourceManifest(
                source_id="hsl_osm_extract", name="HSL-area OpenStreetMap extract",
                source_url="https://karttapalvelu.storage.hsldev.com/hsl.osm/hsl.osm.pbf",
                licence_url="https://www.openstreetmap.org/copyright", licence_id="ODbL-1.0",
                attribution="OpenStreetMap contributors", retrieved_at="2026-08-27T15:17:00+03:00",
                vintage="2026-08-25", coverage="HSL service area",
                checksum="sha256:901a30ce5add6ada15a0279ebf780115ca23ec86d96031a6bdd32b74f3a4304b",
                processing_method="Offline routing and destination extraction",
                caveats=("OSM completeness and routability vary by location.",),
                redistribution_decision="derived_only", rationale="Derived artifacts retain ODbL attribution.",
            ),
            helsinki_buildings_snapshot=arguments.helsinki_buildings_snapshot,
            helsinki_buildings_source_manifest=helsinki_buildings_source_manifest,
            gtfs_source_manifest=SourceManifest(
                source_id="hsl_gtfs", name="HSL GTFS schedules", source_url="https://infopalvelut.storage.hsldev.com/gtfs/hsl.zip",
                licence_url="https://creativecommons.org/licenses/by/4.0/", licence_id="CC-BY-4.0", attribution="HSL",
                retrieved_at="2026-08-27T04:51:22+03:00", vintage="2026-08-27", coverage="HSL service area",
                checksum="sha256:d7baf8c702d7c09f1638df7dcc0f1c89b81aeca01f8371a43f4055dfb937acff",
                processing_method="Offline representative-weekday multimodal routing", caveats=("2026-09-02 representative Wednesday; failures remain partial.",),
                redistribution_decision="allowed", rationale="HSL publishes GTFS as CC BY 4.0.",
            ),
            morning_transit_batch_dir=arguments.morning_transit_batches,
            workplace_transit_batch_dir=arguments.workplace_transit_batches,
            main_cycle_network_snapshot=arguments.main_cycle_network_snapshot,
            main_cycle_network_source_manifest=SourceManifest("helsinki_cycle_network", "Helsinki main cycle routes", "https://kartta.hel.fi/ws/geoserver/avoindata/wfs", "https://creativecommons.org/licenses/by/4.0/", "CC-BY-4.0", "Helsingin kaupunki", "2026-08-31T22:21:00+03:00", "2026-05-12", "Helsinki", "sha256:ec3d379185eede738ea042c47f21712136d42c6807b3ffb9328db4b8d7f28c7a", "Offline distance to published main cycle-route geometry", ("Helsinki only.",), "allowed", "The City of Helsinki publishes the cycling map under CC BY 4.0.") if arguments.main_cycle_network_snapshot else None,
            green_cover_snapshots=tuple(arguments.green_cover_snapshot),
            green_cover_source_manifest=SourceManifest("hsy_green_cover_2024", "HSY 2024 land cover", "https://kartta.hsy.fi/geoserver/wfs", "https://creativecommons.org/licenses/by/4.0/", "CC-BY-4.0", "HSY and municipalities in the region", "2026-08-31T22:22:00+03:00", "2024", "Helsinki, Espoo, Vantaa, Kauniainen", "sha256:a23f9d9e910600a4720e2634b1456bd52753fd95d76bdf5f59b3bb81503b26f6;d5802e9390a7c612599a28f565429806dc326b270ac7051df9988af841f0cf77;3b4a4611b534810d627f6e1d5940ff63d5b404bde39a1ee959d52caff1cf8cf8;64d0fa5eec8e3540425ee689c651ff2da13d03bafe1128e14e0c1ca9525c01f0;939fe1f840380275e905ffcd4be09a70d72c64792d35b715623c447eab738b17", "Offline 300 m vegetation-buffer intersection", ("Land-cover resolution and classification are source-defined.",), "allowed", "HSY publishes the regional land-cover dataset under CC BY 4.0.") if arguments.green_cover_snapshot else None,
            green_cover_checkpoint_dir=arguments.green_cover_checkpoint_dir,
            service_map_snapshot=arguments.service_map_snapshot,
            service_map_source_manifest=service_map_source_manifest,
            ptv_health_snapshot=arguments.ptv_health_snapshot,
            ptv_health_source_manifest=ptv_health_source_manifest,
        )
        return 0
    if arguments.command == "verify-release":
        print(verify_release(arguments.output))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
