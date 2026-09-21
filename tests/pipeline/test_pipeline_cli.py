from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "release_fixture.json"
HSY_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "hsy_buildings.geojson"
PAAVO_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "paavo_areas.geojson"
NOISE_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "helsinki_noise_2022.geojson"
VANTAA_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "vantaa_property_map.geojson"
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
            "--vantaa-property-snapshot", str(VANTAA_FIXTURE_PATH),
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
