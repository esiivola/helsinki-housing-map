from __future__ import annotations

import subprocess
import sys
import gzip
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "release_fixture.json"
HSY_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "hsy_buildings.geojson"
PAAVO_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "paavo_areas.geojson"
NOISE_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "helsinki_noise_2022.geojson"
OSM_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "osm_destinations.osm"


def test_fixture_release_command_writes_static_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "bundle"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pipeline",
            "fixture-release",
            str(FIXTURE_PATH),
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "manifest.json").is_file()


def test_hsy_release_command_writes_partitioned_static_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "bundle"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pipeline",
            "hsy-release",
            str(HSY_FIXTURE_PATH),
            str(output_dir),
            "--retrieved-at",
            "2026-08-26T23:15:17+03:00",
            "--vintage",
            "2026-08-26",
            "--checksum",
            "sha256:fixture",
            "--paavo-snapshot", str(PAAVO_FIXTURE_PATH),
            "--noise-snapshot", str(NOISE_FIXTURE_PATH),
            "--night-noise-snapshot", str(NOISE_FIXTURE_PATH),
            "--osm-snapshot", str(OSM_FIXTURE_PATH),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "geometry" / "Helsinki.geojson.gz").is_file()
    assert "paavo_income" in (output_dir / "sources.json").read_text()


def test_hsy_release_rejects_espoo_city_land_snapshot_without_provenance(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable, "-m", "pipeline", "hsy-release", str(HSY_FIXTURE_PATH), str(tmp_path / "bundle"),
            "--retrieved-at", "2026-08-26T23:15:17+03:00", "--vintage", "2026-08-26", "--checksum", "sha256:fixture",
            "--espoo-city-land-snapshot", str(tmp_path / "city-land.gml"),
        ],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert "--espoo-city-land-snapshot requires retrieved-at, vintage, and checksum" in result.stderr


def test_hsy_release_rejects_espoo_buildings_snapshot_without_provenance(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable, "-m", "pipeline", "hsy-release", str(HSY_FIXTURE_PATH), str(tmp_path / "bundle"),
            "--retrieved-at", "2026-08-26T23:15:17+03:00", "--vintage", "2026-08-26", "--checksum", "sha256:fixture",
            "--espoo-buildings-snapshot", str(tmp_path / "espoo-buildings.gml"),
        ],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert "--espoo-buildings-snapshot requires retrieved-at, vintage, and checksum" in result.stderr


def test_hsy_release_rejects_helsinki_ownership_snapshot_without_complete_provenance(tmp_path: Path) -> None:
    snapshot = tmp_path / "building_ownership.csv"
    snapshot.write_text("building_id,luokka\nfixture-1,kaupunki\n")

    result = subprocess.run(
        [
            sys.executable, "-m", "pipeline", "hsy-release", str(HSY_FIXTURE_PATH), str(tmp_path / "bundle"),
            "--retrieved-at", "2026-08-26T23:15:17+03:00", "--vintage", "2026-08-26", "--checksum", "sha256:fixture",
            "--helsinki-building-ownership-snapshot", str(snapshot),
        ],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert "--helsinki-building-ownership-snapshot requires complete provenance" in result.stderr


def test_hsy_release_publishes_helsinki_ownership_with_complete_provenance(tmp_path: Path) -> None:
    snapshot = tmp_path / "building_ownership.csv"
    snapshot.write_text("building_id,luokka\nfixture-1,kaupunki\n")
    output = tmp_path / "bundle"

    result = subprocess.run(
        [
            sys.executable, "-m", "pipeline", "hsy-release", str(HSY_FIXTURE_PATH), str(output),
            "--retrieved-at", "2026-08-26T23:15:17+03:00", "--vintage", "2026-08-26", "--checksum", "sha256:fixture",
            "--paavo-snapshot", str(PAAVO_FIXTURE_PATH), "--noise-snapshot", str(NOISE_FIXTURE_PATH),
            "--night-noise-snapshot", str(NOISE_FIXTURE_PATH), "--osm-snapshot", str(OSM_FIXTURE_PATH),
            "--helsinki-building-ownership-snapshot", str(snapshot),
            "--helsinki-building-ownership-retrieved-at", "2026-09-22T12:00:00+03:00",
            "--helsinki-building-ownership-vintage", "2026-09-22",
            "--helsinki-building-ownership-checksum", "sha256:fixture",
        ],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    sources = json.loads((output / "sources.json").read_text())
    source = next(source for source in sources if source["source_id"] == "helsinki_building_ownership")
    assert source["name"] == "Helsinki public rental decisions"
    assert source["source_url"] == "https://paatokset.hel.fi/fi/"
    assert source["redistribution_decision"] == "derived_only"
    attributes = json.loads(gzip.decompress((output / "attributes" / "Helsinki.json.gz").read_bytes()))
    owner = next(value for value in attributes["building_values"] if value["layer_id"] == "land_owner_class")
    assert owner["value"] == "city"


def test_transit_batch_command_reports_a_missing_otp_jar_before_reading_inputs(tmp_path: Path) -> None:
    missing_jar = tmp_path / "otp-shaded-2.9.0.jar"

    result = subprocess.run(
        [
            sys.executable, "scripts/build_transit_batches.py", str(tmp_path / "buildings.geojson"),
            "--osm", str(tmp_path / "map.pbf"), "--gtfs", str(tmp_path / "gtfs.zip"),
            "--java", sys.executable, "--jar", str(missing_jar), "--output", str(tmp_path / "output"),
        ],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )

    assert result.returncode == 2
    assert f"OTP JAR not found: {missing_jar}" in result.stderr
