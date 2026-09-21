from __future__ import annotations

import csv
import json
import os
import socket
import subprocess
import tempfile
import time as clock
from bisect import bisect_left
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from io import TextIOWrapper
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState


MORNING_RANGE_ITINERARY_DETAIL_VERSION = 4


class OpenTripPlannerQueryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Connection:
    departure: int
    arrival: int
    departure_stop: str
    arrival_stop: str


@dataclass(frozen=True)
class TransitItinerary:
    duration_seconds: float
    transfers: int
    walk_seconds: float
    transport_modes: tuple[str, ...] = ()
    boardings: int = 0
    first_boarding_walk_m: float | None = None
    start_time_ms: int | None = None
    end_time_ms: int | None = None


@dataclass(frozen=True)
class TransitSample:
    departure_time: str
    itinerary: TransitItinerary | None


def read_gtfs_connections(path: Path, service_date: date) -> list[Connection]:
    with ZipFile(path) as archive:
        active_services = _active_services(archive, service_date)
        active_trips = {
            row["trip_id"]
            for row in _rows(archive, "trips.txt")
            if row["service_id"] in active_services
        }
        connections: list[Connection] = []
        previous_by_trip: dict[str, tuple[str, int]] = {}
        for row in _rows(archive, "stop_times.txt"):
            trip_id = row["trip_id"]
            if trip_id not in active_trips:
                continue
            arrival = _seconds(row["arrival_time"])
            departure = _seconds(row["departure_time"])
            if previous := previous_by_trip.get(trip_id):
                previous_stop, previous_departure = previous
                connections.append(Connection(previous_departure, arrival, previous_stop, row["stop_id"]))
            previous_by_trip[trip_id] = (row["stop_id"], departure)
    return sorted(connections, key=lambda connection: connection.departure, reverse=True)


def journey_profiles(connections: list[Connection], destination_stops: set[str]) -> dict[str, tuple[tuple[int, int], ...]]:
    profiles: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for stop_id in destination_stops:
        profiles[stop_id].append((0, 0))
    for connection in connections:
        arrival = _arrival_after(profiles.get(connection.arrival_stop, ()), connection.arrival)
        if arrival is None:
            continue
        current = _arrival_after(profiles.get(connection.departure_stop, ()), connection.departure)
        if current is None or arrival < current:
            profiles[connection.departure_stop].append((connection.departure, arrival))
    return {stop_id: tuple(reversed(profile)) for stop_id, profile in profiles.items()}


def fastest_arrival(profile: tuple[tuple[int, int], ...], departure: int) -> int | None:
    if profile == ((0, 0),):
        return departure
    index = bisect_left(profile, (departure, -1))
    return profile[index][1] if index < len(profile) else None


def fastest_journey_minutes(
    profiles: dict[str, tuple[tuple[int, int], ...]],
    access_seconds: dict[str, int],
    departure: int,
) -> float | None:
    arrivals = (
        fastest_arrival(profiles[stop_id], departure + walk_seconds)
        for stop_id, walk_seconds in access_seconds.items()
        if stop_id in profiles
    )
    successful = [arrival for arrival in arrivals if arrival is not None]
    return (min(successful) - departure) / 60 if successful else None


def aggregate_sampled_journeys(samples: list[float | None]) -> BuildingValue:
    successful = [duration for duration in samples if duration is not None]
    if not successful:
        return BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
    return BuildingValue(
        ValueState.KNOWN if len(successful) == len(samples) else ValueState.PARTIAL,
        ValueKind.SCALAR,
        max(successful),
        coverage=len(successful) / len(samples),
        method=ValueMethod.DERIVED,
        confidence=Confidence.MEDIUM,
    )


def otp_fastest_itinerary(endpoint: str, origin: tuple[float, float], destination: tuple[float, float], service_date: str, time: str) -> TransitItinerary | None:
    query = {
        "query": "{ plan(from: {lat: %s, lon: %s}, to: {lat: %s, lon: %s}, date: \"%s\", time: \"%s\", transportModes: [{mode: WALK}, {mode: TRANSIT}]) { itineraries { duration numberOfTransfers walkTime legs { mode distance } } } }"
        % (*origin, *destination, service_date, time)
    }
    request = Request(endpoint, data=json.dumps(query).encode(), headers={"content-type": "application/json"})
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if errors := payload.get("errors"):
        raise OpenTripPlannerQueryError("OpenTripPlanner query failed: " + "; ".join(error.get("message", "unknown error") for error in errors))
    itineraries = payload.get("data", {}).get("plan", {}).get("itineraries", [])
    candidates = [itinerary for item in itineraries if (itinerary := _parse_otp_itinerary(item)) is not None]
    return min(candidates, key=lambda item: (item.duration_seconds, item.transfers, item.walk_seconds), default=None)


def _parse_otp_itinerary(item: object) -> TransitItinerary | None:
    if not isinstance(item, dict) or any(item.get(field) is None for field in ("duration", "numberOfTransfers", "walkTime")):
        return None
    legs = item.get("legs")
    if not isinstance(legs, list) or any(not isinstance(leg, dict) or not isinstance(leg.get("mode"), str) for leg in legs):
        return None
    boardings = sum(leg["mode"] != "WALK" for leg in legs)
    first_boarding_walk_m: float | None = None
    if boardings:
        leading_walks = legs[:next(index for index, leg in enumerate(legs) if leg["mode"] != "WALK")]
        if any(not isinstance(leg.get("distance"), (int, float)) for leg in leading_walks):
            return None
        first_boarding_walk_m = sum(float(leg["distance"]) for leg in leading_walks)
    start_time_ms = item.get("startTime")
    end_time_ms = item.get("endTime")
    if (start_time_ms is not None or end_time_ms is not None) and (
        not isinstance(start_time_ms, int) or not isinstance(end_time_ms, int)
    ):
        return None
    return TransitItinerary(
        item["duration"], item["numberOfTransfers"], item["walkTime"],
        tuple(sorted({leg["mode"] for leg in legs if leg["mode"] != "WALK"})), boardings, first_boarding_walk_m, start_time_ms, end_time_ms,
    )


def otp_range_itineraries(
    endpoint: str,
    origin: tuple[float, float],
    destination: tuple[float, float],
    service_date: str | date,
    start_time: str,
    search_window_seconds: int,
) -> list[TransitItinerary]:
    earliest_departure = _service_moment(service_date, start_time)
    latest_departure_ms = int((earliest_departure + timedelta(seconds=search_window_seconds)).timestamp() * 1_000)
    after: str | None = None
    itineraries: list[TransitItinerary] = []
    while True:
        after_argument = f", after: {json.dumps(after)}" if after is not None else ""
        query = {
            "query": "{ planConnection(origin: {location: {coordinate: {latitude: %s, longitude: %s}}}, destination: {location: {coordinate: {latitude: %s, longitude: %s}}}, dateTime: {earliestDeparture: \"%s\"}, modes: {transitOnly: true}, searchWindow: \"PT%sS\", first: 100%s) { edges { cursor node { startTime endTime duration numberOfTransfers walkTime legs { mode distance } } } pageInfo { hasNextPage endCursor } } }"
            % (*origin, *destination, earliest_departure.isoformat(), search_window_seconds, after_argument)
        }
        request = Request(endpoint, data=json.dumps(query).encode(), headers={"content-type": "application/json"})
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
        if errors := payload.get("errors"):
            raise OpenTripPlannerQueryError("OpenTripPlanner query failed: " + "; ".join(error.get("message", "unknown error") for error in errors))
        connection = payload.get("data", {}).get("planConnection", {})
        if not isinstance(connection, dict):
            raise OpenTripPlannerQueryError("OpenTripPlanner range query returned an invalid connection")
        edges = connection.get("edges", [])
        page = connection.get("pageInfo", {})
        if not isinstance(edges, list) or not isinstance(page, dict) or not isinstance(page.get("hasNextPage"), bool):
            raise OpenTripPlannerQueryError("OpenTripPlanner range query returned an invalid page")
        page_itineraries = [itinerary for edge in edges if (itinerary := _parse_otp_itinerary(edge.get("node") if isinstance(edge, dict) else None)) is not None]
        if len(page_itineraries) != len(edges) or any(itinerary.start_time_ms is None or itinerary.end_time_ms is None for itinerary in page_itineraries):
            raise OpenTripPlannerQueryError("OpenTripPlanner range query returned an incomplete itinerary")
        itineraries.extend(itinerary for itinerary in page_itineraries if itinerary.start_time_ms is not None and itinerary.start_time_ms <= latest_departure_ms)
        if not page.get("hasNextPage") or not page_itineraries or all(itinerary.start_time_ms is not None and itinerary.start_time_ms > latest_departure_ms for itinerary in page_itineraries):
            return itineraries
        next_after = page.get("endCursor")
        if not isinstance(next_after, str) or next_after == after:
            raise OpenTripPlannerQueryError("OpenTripPlanner range pagination did not provide a usable next cursor")
        after = next_after


def route_morning_range_origin_samples(
    endpoint: str,
    origins: dict[str, tuple[float, float]],
    destination: tuple[float, float],
    service_date: str | date,
    times: list[str],
    maximum_initial_wait_minutes: int,
    workers: int,
) -> dict[str, list[TransitSample]]:
    if not times:
        return {building_id: [] for building_id in origins}
    requested_moments = {departure_time: _service_moment(service_date, departure_time) for departure_time in times}
    search_window_seconds = int((max(requested_moments.values()) - min(requested_moments.values())).total_seconds()) + maximum_initial_wait_minutes * 60

    def route(origin: tuple[float, float]) -> list[TransitSample]:
        try:
            itineraries = otp_range_itineraries(endpoint, origin, destination, service_date, times[0], search_window_seconds)
        except (OSError, TimeoutError, ValueError, OpenTripPlannerQueryError):
            return [TransitSample(departure_time, None) for departure_time in times]
        samples = []
        for departure_time, requested_moment in requested_moments.items():
            requested_ms = int(requested_moment.timestamp() * 1_000)
            latest_start_ms = requested_ms + maximum_initial_wait_minutes * 60_000
            candidates = [itinerary for itinerary in itineraries if itinerary.start_time_ms is not None and itinerary.end_time_ms is not None and requested_ms <= itinerary.start_time_ms <= latest_start_ms]
            selected = min(candidates, key=lambda itinerary: (itinerary.end_time_ms, itinerary.boardings, itinerary.first_boarding_walk_m if itinerary.first_boarding_walk_m is not None else float("inf"), itinerary.walk_seconds), default=None)
            samples.append(TransitSample(departure_time, replace(selected, duration_seconds=(selected.end_time_ms - requested_ms) / 1_000) if selected is not None else None))
        return samples

    with ThreadPoolExecutor(max_workers=workers) as executor:
        values = executor.map(route, origins.values())
        return dict(zip(origins, values, strict=True))


def _service_moment(service_date: str | date, departure_time: str) -> datetime:
    return datetime.combine(date.fromisoformat(service_date) if isinstance(service_date, str) else service_date, time.fromisoformat(departure_time), tzinfo=ZoneInfo("Europe/Helsinki"))


def otp_journey_minutes(endpoint: str, origin: tuple[float, float], destination: tuple[float, float], service_date: str, time: str) -> float | None:
    itinerary = otp_fastest_itinerary(endpoint, origin, destination, service_date, time)
    return itinerary.duration_seconds / 60 if itinerary is not None else None


def route_sampled_origin_samples(
    endpoint: str,
    origins: dict[str, tuple[float, float]],
    destination: tuple[float, float],
    service_date: str,
    times: list[str],
    workers: int,
) -> dict[str, list[TransitSample]]:
    def route(origin: tuple[float, float]) -> list[TransitSample]:
        samples: list[TransitSample] = []
        for time in times:
            try:
                samples.append(TransitSample(time, otp_fastest_itinerary(endpoint, origin, destination, service_date, time)))
            except (OSError, TimeoutError, ValueError, OpenTripPlannerQueryError):
                samples.append(TransitSample(time, None))
        return samples

    with ThreadPoolExecutor(max_workers=workers) as executor:
        values = executor.map(route, origins.values())
        return dict(zip(origins, values, strict=True))


def route_sampled_origins(
    endpoint: str,
    origins: dict[str, tuple[float, float]],
    destination: tuple[float, float],
    service_date: str,
    times: list[str],
    workers: int,
) -> dict[str, BuildingValue]:
    def route(origin: tuple[float, float]) -> BuildingValue:
        samples: list[float | None] = []
        for time in times:
            try:
                samples.append(otp_journey_minutes(endpoint, origin, destination, service_date, time))
            except (OSError, TimeoutError, ValueError, OpenTripPlannerQueryError):
                samples.append(None)
        return aggregate_sampled_journeys(samples)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        values = executor.map(route, origins.values())
        return dict(zip(origins, values, strict=True))


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@contextmanager
def local_otp_server(java: Path, jar: Path, osm: Path, gtfs: Path, port: int | None = None):
    port = available_port() if port is None else port
    with tempfile.TemporaryDirectory(prefix="helsinki-otp-") as directory:
        workdir = Path(directory)
        os.symlink(osm.resolve(), workdir / osm.name)
        os.symlink(gtfs.resolve(), workdir / gtfs.name)
        subprocess.run([str(java), "-Xmx8G", "-jar", str(jar), "--build", "--save", str(workdir)], check=True)
        process = subprocess.Popen([str(java), "-Xmx8G", "-jar", str(jar), "--load", "--serve", "--port", str(port), str(workdir)])
        endpoint = f"http://127.0.0.1:{port}/otp/routers/default/index/graphql"
        try:
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError("OpenTripPlanner stopped before becoming ready")
                try:
                    otp_journey_minutes(endpoint, (60.1699, 24.9384), (60.1719, 24.9412), "2026-09-02", "07:00")
                    break
                except (OSError, TimeoutError, ValueError):
                    clock.sleep(1)
            else:
                raise TimeoutError("OpenTripPlanner did not become ready")
            yield endpoint
        finally:
            process.terminate()
            process.wait(timeout=30)


def _active_services(archive: ZipFile, service_date: date) -> set[str]:
    weekday = service_date.strftime("%A").lower()
    date_text = service_date.strftime("%Y%m%d")
    services = {
        row["service_id"]
        for row in _rows(archive, "calendar.txt")
        if row[weekday] == "1" and row["start_date"] <= date_text <= row["end_date"]
    }
    for row in _rows(archive, "calendar_dates.txt"):
        if row["date"] == date_text:
            if row["exception_type"] == "1":
                services.add(row["service_id"])
            elif row["exception_type"] == "2":
                services.discard(row["service_id"])
    return services


def _rows(archive: ZipFile, name: str):
    with archive.open(name) as raw:
        yield from csv.DictReader(TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def _seconds(value: str) -> int:
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3_600 + minutes * 60 + seconds


def _arrival_after(profile: list[tuple[int, int]] | tuple[tuple[int, int], ...], departure: int) -> int | None:
    if profile == [(0, 0)] or profile == ((0, 0),):
        return departure
    for profile_departure, arrival in reversed(profile):
        if profile_departure >= departure:
            return arrival
    return None
