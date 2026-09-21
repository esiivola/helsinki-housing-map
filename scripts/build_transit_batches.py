from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

sys.path.insert(0, str(Path(__file__).parents[1]))

from pipeline.sources.hsy_buildings import normalize_hsy_buildings, read_hsy_buildings
from pipeline.sources.transit import MORNING_RANGE_ITINERARY_DETAIL_VERSION, TransitSample, local_otp_server, route_morning_range_origin_samples, route_sampled_origin_samples

ITINERARY_DETAIL_VERSION = MORNING_RANGE_ITINERARY_DETAIL_VERSION


def scored_buildings(raw):
    return [(index, building) for index, building in zip(raw.index, normalize_hsy_buildings(raw), strict=True) if building.is_scored]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build resumable local OTP transit batches.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--osm", type=Path, required=True)
    parser.add_argument("--gtfs", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--morning-commute", action="store_true", help="Use a Wednesday 07:00–08:00 minute-level range profile.")
    parser.add_argument("--workplace-commute", action="store_true", help="Route the morning commute to all configured workplace destinations.")
    args = parser.parse_args()
    if not args.jar.is_file():
        parser.error(f"OTP JAR not found: {args.jar}. Download OpenTripPlanner 2.9.0 to a durable local path before running this command.")

    routing = yaml.safe_load((Path(__file__).parents[1] / "pipeline" / "config" / "routing.yaml").read_text())
    if args.morning_commute or args.workplace_commute:
        routing["transit"]["samples"] = morning_commute_times()
    raw = read_hsy_buildings(args.snapshot, {"vtj_prt", "raktun", "kavu", "kayttarks", "kunta"}, source_crs=3879)
    scored = scored_buildings(raw)
    destinations = workplace_destinations(routing) if args.workplace_commute else [{"id": "central", **routing["central_destination"]}]

    with local_otp_server(args.java, args.jar, args.osm, args.gtfs) as endpoint:
        for destination in destinations:
            output_directory = args.output / destination["id"] if args.workplace_commute else args.output
            output_directory.mkdir(parents=True, exist_ok=True)
            for batch_index, start in enumerate(range(0, len(scored), args.batch_size)):
                if args.max_batches is not None and batch_index >= args.max_batches:
                    break
                output = output_directory / f"transit-{batch_index:04d}.parquet"
                parameters = {**routing["transit"], "destination": destination, "itinerary_detail_version": ITINERARY_DETAIL_VERSION}
                if _valid_batch(output, min(args.batch_size, len(scored) - start), len(routing["transit"]["samples"]), parameters):
                    continue
                print(f"{destination['id']}: batch {batch_index}", flush=True)
                batch = scored[start : start + args.batch_size]
                frame = raw.loc[[index for index, _ in batch]].to_crs(4326)
                origins = {
                    building.building_id: (point.y, point.x)
                    for (_, building), point in zip(batch, frame.geometry.representative_point(), strict=True)
                    if point.is_valid and not point.is_empty and math.isfinite(point.x) and math.isfinite(point.y)
                }
                if args.morning_commute or args.workplace_commute:
                    samples_by_building = route_morning_range_origin_samples(
                        endpoint, origins,
                        (destination["latitude"], destination["longitude"]),
                        routing["transit"]["service_date"], routing["transit"]["samples"], routing["transit"]["morning_maximum_initial_wait_minutes"], routing["transit"]["workers"],
                    )
                else:
                    samples_by_building = route_sampled_origin_samples(
                        endpoint, origins,
                        (destination["latitude"], destination["longitude"]),
                        routing["transit"]["service_date"], routing["transit"]["samples"], routing["transit"]["workers"],
                    )
                for _, building in batch:
                    samples_by_building.setdefault(building.building_id, [TransitSample(time, None) for time in routing["transit"]["samples"]])
                _write_samples(output, samples_by_building, parameters)
    return 0


def morning_commute_times() -> list[str]:
    return [f"{hour:02d}:{minute:02d}" for hour in range(7, 9) for minute in range(60) if hour < 8 or minute == 0]


def workplace_destinations(routing: dict) -> list[dict]:
    return [*routing["workplace_destinations"], {"id": "rautatieasema", **routing["central_destination"]}]


def _valid_batch(path: Path, expected: int, sample_count: int | None = None, parameters: dict | None = None) -> bool:
    if not path.is_file():
        return False
    if path.suffix == ".parquet":
        try:
            metadata = pq.read_metadata(path)
            if metadata.num_rows != expected * sample_count:
                return False
            if parameters is not None:
                stored = metadata.metadata.get(b"transit_parameters") if metadata.metadata else None
                return stored is not None and _outcome_parameters(json.loads(stored)) == _outcome_parameters(json_safe(parameters))
            return True
        except (OSError, ValueError, pa.ArrowException):
            return False
    try:
        return len(json.loads(path.read_text())["values"]) == expected
    except (KeyError, ValueError):
        return False


def _write_samples(path: Path, samples_by_building: dict[str, list[TransitSample]], parameters: dict) -> None:
    rows = [
        {
            "building_id": building_id,
            "departure_time": sample.departure_time,
            "state": "known" if sample.itinerary is not None else "unknown",
            "duration_seconds": sample.itinerary.duration_seconds if sample.itinerary is not None else None,
            "transfers": sample.itinerary.transfers if sample.itinerary is not None else None,
            "walk_seconds": sample.itinerary.walk_seconds if sample.itinerary is not None else None,
            "transport_modes": list(sample.itinerary.transport_modes) if sample.itinerary is not None else None,
            "boardings": sample.itinerary.boardings if sample.itinerary is not None else None,
            "first_boarding_walk_m": sample.itinerary.first_boarding_walk_m if sample.itinerary is not None else None,
            "itinerary_start_time_ms": sample.itinerary.start_time_ms if sample.itinerary is not None else None,
            "itinerary_end_time_ms": sample.itinerary.end_time_ms if sample.itinerary is not None else None,
        }
        for building_id, samples in samples_by_building.items()
        for sample in samples
    ]
    table = pa.Table.from_pylist(rows).replace_schema_metadata({b"transit_parameters": json.dumps(json_safe(parameters), sort_keys=True).encode()})
    temporary = path.with_suffix(".partial.parquet")
    pq.write_table(table, temporary)
    temporary.replace(path)


def _outcome_parameters(parameters: dict) -> dict:
    return {key: value for key, value in parameters.items() if key != "workers"}


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value.isoformat() if hasattr(value, "isoformat") else value


if __name__ == "__main__":
    raise SystemExit(main())
