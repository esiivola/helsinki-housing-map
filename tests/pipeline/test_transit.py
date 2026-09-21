from datetime import date, datetime
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import yaml

from pipeline.models import ValueState
from pipeline.sources import transit
from pipeline.sources.transit import TransitItinerary, TransitSample, aggregate_sampled_journeys, available_port, fastest_arrival, fastest_journey_minutes, journey_profiles, read_gtfs_connections, otp_fastest_itinerary
from scripts.build_transit_batches import _valid_batch, _write_samples, json_safe, morning_commute_times, scored_buildings, workplace_destinations


def test_gtfs_profiles_choose_the_fastest_continuation_after_walking_access(tmp_path: Path) -> None:
    snapshot = tmp_path / "fixture.zip"
    with ZipFile(snapshot, "w") as archive:
        archive.writestr("calendar.txt", "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nweekday,0,0,1,0,0,0,0,20260831,20261024\n")
        archive.writestr("calendar_dates.txt", "service_id,date,exception_type\n")
        archive.writestr("trips.txt", "route_id,service_id,trip_id\nr,weekday,slow\nr,weekday,fast\n")
        archive.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nslow,07:10:00,07:10:00,A,1\nslow,07:30:00,07:30:00,C,2\nfast,07:20:00,07:20:00,B,1\nfast,07:25:00,07:25:00,C,2\n")

    profiles = journey_profiles(read_gtfs_connections(snapshot, date(2026, 9, 2)), {"C"})

    assert fastest_arrival(profiles["A"], 7 * 3_600) == 7 * 3_600 + 30 * 60
    assert fastest_journey_minutes(profiles, {"A": 0, "B": 15 * 60}, 7 * 3_600) == 25


def test_gtfs_profiles_return_unknown_when_no_candidate_stop_can_reach_destination() -> None:
    assert fastest_journey_minutes({}, {"A": 0}, 7 * 3_600) is None


def test_sampled_journeys_use_the_worst_success_and_preserve_failed_samples() -> None:
    value = aggregate_sampled_journeys([31.5, None, 28.0])

    assert value.state is ValueState.PARTIAL
    assert value.value == 31.5
    assert value.coverage == 2 / 3


def test_parallel_router_preserves_each_building_sample_failures(monkeypatch) -> None:
    def route(_endpoint, origin, _destination, _date, time):
        return None if origin[0] == 2 and time == "07:30" else float(time[-2:])

    monkeypatch.setattr(transit, "otp_journey_minutes", route)
    values = transit.route_sampled_origins("http://127.0.0.1", {"a": (1, 1), "b": (2, 2)}, (3, 3), "2026-09-02", ["07:00", "07:30"], 2)

    assert values["a"].state is ValueState.KNOWN
    assert values["a"].value == 30
    assert values["b"].state is ValueState.PARTIAL


def test_parallel_router_turns_an_individual_router_error_into_a_partial_value(monkeypatch) -> None:
    def route(_endpoint, _origin, _destination, _date, time):
        if time == "07:30":
            raise TimeoutError
        return 20.0

    monkeypatch.setattr(transit, "otp_journey_minutes", route)
    value = transit.route_sampled_origins("http://127.0.0.1", {"a": (1, 1)}, (3, 3), "2026-09-02", ["07:00", "07:30"], 1)["a"]

    assert value.state is ValueState.PARTIAL


def test_detailed_parallel_router_keeps_a_graphql_worker_error_as_an_unknown_sample(monkeypatch) -> None:
    def route(_endpoint, _origin, _destination, _date, time):
        if time == "07:15":
            raise transit.OpenTripPlannerQueryError("OpenTripPlanner query failed: internal routing error")
        return TransitItinerary(120, 1, 30)

    monkeypatch.setattr(transit, "otp_fastest_itinerary", route)

    samples = transit.route_sampled_origin_samples("http://127.0.0.1", {"a": (1, 1)}, (3, 3), "2026-09-02", ["07:00", "07:15"], 1)["a"]

    assert samples == [TransitSample("07:00", TransitItinerary(120, 1, 30)), TransitSample("07:15", None)]


def test_transit_batch_normalizes_raw_hsy_rows_with_its_known_source_id() -> None:
    import geopandas as gpd
    from shapely.geometry import Point

    raw = gpd.GeoDataFrame({"vtj_prt": ["a"], "raktun": ["b"], "kavu": [1970], "kayttarks": ["Asuinrakennus"], "kunta": ["091"]}, geometry=[Point(24.9, 60.2)], crs=4326)

    assert [building.building_id for _, building in scored_buildings(raw)] == ["a"]


def test_otp_port_selector_asks_the_os_for_an_ephemeral_loopback_port(monkeypatch) -> None:
    class Listener:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def bind(self, address):
            assert address == ("127.0.0.1", 0)

        def getsockname(self):
            return ("127.0.0.1", 43123)

    monkeypatch.setattr(transit.socket, "socket", lambda *_args: Listener())

    assert available_port() == 43123


def test_transit_batch_parameters_serialize_yaml_dates() -> None:
    assert json_safe({"service_date": date(2026, 9, 2)}) == {"service_date": "2026-09-02"}


def test_morning_commute_uses_every_minute_from_seven_to_eight_inclusive() -> None:
    times = morning_commute_times()

    assert len(times) == 61
    assert times[0] == "07:00"
    assert times[-1] == "08:00"


def test_range_router_accepts_the_service_date_type_loaded_from_yaml() -> None:
    moment = transit._service_moment(date(2026, 9, 23), "07:00")

    assert moment.isoformat() == "2026-09-23T07:00:00+03:00"


def test_range_router_expands_a_single_itinerary_array_into_wait_inclusive_minute_samples(monkeypatch) -> None:
    def milliseconds(time: str) -> int:
        return int(datetime.fromisoformat(f"2026-09-23T{time}:00+03:00").timestamp() * 1_000)

    monkeypatch.setattr(
        transit,
        "otp_range_itineraries",
        lambda *_args: [
            TransitItinerary(28 * 60, 0, 120, ("BUS",), 1, 100, milliseconds("07:02"), milliseconds("07:30")),
            TransitItinerary(21 * 60, 1, 180, ("BUS", "TRAM"), 2, 50, milliseconds("07:04"), milliseconds("07:25")),
            TransitItinerary(30 * 60, 0, 120, ("RAIL",), 1, 80, milliseconds("07:10"), milliseconds("07:40")),
        ],
    )

    samples = transit.route_morning_range_origin_samples(
        "http://127.0.0.1", {"a": (60.1, 24.9)}, (60.2, 24.8), "2026-09-23",
        ["07:00", "07:03", "07:05", "07:11"], 5, 1,
    )["a"]

    assert samples == [
        TransitSample("07:00", TransitItinerary(25 * 60, 1, 180, ("BUS", "TRAM"), 2, 50, milliseconds("07:04"), milliseconds("07:25"))),
        TransitSample("07:03", TransitItinerary(22 * 60, 1, 180, ("BUS", "TRAM"), 2, 50, milliseconds("07:04"), milliseconds("07:25"))),
        TransitSample("07:05", TransitItinerary(35 * 60, 0, 120, ("RAIL",), 1, 80, milliseconds("07:10"), milliseconds("07:40"))),
        TransitSample("07:11", None),
    ]


def test_workplace_destinations_include_every_configured_commute_target() -> None:
    routing = yaml.safe_load((Path(__file__).parents[2] / "pipeline" / "config" / "routing.yaml").read_text())

    assert [destination["id"] for destination in workplace_destinations(routing)] == [
        "ruoholahti", "keilaniemi", "kamppi", "pasila", "kalasatama", "tapiola",
        "leppavaara", "aviapolis", "tikkurila", "myyrmaki", "rautatieasema",
    ]
    configured = {destination["id"]: (destination["latitude"], destination["longitude"]) for destination in workplace_destinations(routing)}
    assert configured["keilaniemi"] == (60.1771, 24.8307)
    assert configured["aviapolis"] == (60.3043, 24.9564)
    assert configured["tikkurila"] == (60.2923, 25.0441)


def test_workplace_commute_uses_the_selected_september_23_service_date() -> None:
    routing = yaml.safe_load((Path(__file__).parents[2] / "pipeline" / "config" / "routing.yaml").read_text())

    assert routing["transit"]["service_date"] == date(2026, 9, 23)


def test_otp_query_errors_are_not_silently_treated_as_no_route(monkeypatch) -> None:
    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(transit, "urlopen", lambda *_args, **_kwargs: Response(b'{"errors":[{"message":"invalid date"}]}'))

    import pytest

    with pytest.raises(RuntimeError, match="invalid date"):
        transit.otp_journey_minutes("http://127.0.0.1", (60.1, 24.9), (60.2, 24.8), "2026-09-02", "07:00")


def test_otp_query_emits_graphql_string_quotes_without_backslashes(monkeypatch) -> None:
    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    received = {}

    def open_request(request, **_kwargs):
        received["query"] = json.loads(request.data)["query"]
        return Response(b'{"data":{"plan":{"itineraries":[{"duration":60,"numberOfTransfers":0,"walkTime":30,"legs":[{"mode":"WALK","distance":80},{"mode":"TRAM","distance":200}]}]}}}')

    monkeypatch.setattr(transit, "urlopen", open_request)

    assert transit.otp_journey_minutes("http://127.0.0.1", (60.1, 24.9), (60.2, 24.8), "2026-09-02", "07:00") == 1
    assert 'date: "2026-09-02"' in received["query"]
    assert "legs { mode distance }" in received["query"]
    assert '\\\\"' not in received["query"]


def test_otp_range_query_pages_itineraries_until_the_search_window_is_complete(monkeypatch) -> None:
    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    requests = []
    payloads = [
        {"data": {"planConnection": {"edges": [{"cursor": "first", "node": {"startTime": 1_790_000_000_000, "endTime": 1_790_000_900_000, "duration": 900, "numberOfTransfers": 0, "walkTime": 60, "legs": [{"mode": "WALK", "distance": 80}, {"mode": "BUS", "distance": 500}]}}], "pageInfo": {"hasNextPage": True, "endCursor": "first"}}}},
        {"data": {"planConnection": {"edges": [{"cursor": "second", "node": {"startTime": 1_790_000_600_000, "endTime": 1_790_001_500_000, "duration": 900, "numberOfTransfers": 1, "walkTime": 90, "legs": [{"mode": "TRAM", "distance": 500}]}}], "pageInfo": {"hasNextPage": False, "endCursor": "second"}}}},
    ]

    def open_request(request, **_kwargs):
        requests.append(json.loads(request.data)["query"])
        return Response(json.dumps(payloads.pop(0)).encode())

    monkeypatch.setattr(transit, "urlopen", open_request)

    itineraries = transit.otp_range_itineraries("http://127.0.0.1", (60.1, 24.9), (60.2, 24.8), "2026-09-23", "07:00", 7_200)

    assert len(itineraries) == 2
    assert itineraries[0].first_boarding_walk_m == 80
    assert "planConnection" in requests[0]
    assert "modes: {transitOnly: true}" in requests[0]
    assert 'searchWindow: "PT7200S"' in requests[0]
    assert 'after: "first"' in requests[1]


def test_otp_keeps_transfer_and_walk_details_of_the_fastest_itinerary(monkeypatch) -> None:
    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    payload = b'{"data":{"plan":{"itineraries":[{"duration":120,"numberOfTransfers":1,"walkTime":40,"legs":[{"mode":"BUS","distance":100}]},{"duration":120,"numberOfTransfers":0,"walkTime":60,"legs":[{"mode":"WALK","distance":90},{"mode":"TRAM","distance":200},{"mode":"WALK","distance":30},{"mode":"TRAM","distance":300}]},{"duration":180,"numberOfTransfers":0,"walkTime":10,"legs":[{"mode":"RAIL","distance":100}]}]}}}'
    monkeypatch.setattr(transit, "urlopen", lambda *_args, **_kwargs: Response(payload))

    itinerary = otp_fastest_itinerary("http://127.0.0.1", (60.1, 24.9), (60.2, 24.8), "2026-09-02", "07:00")

    assert itinerary.duration_seconds == 120
    assert itinerary.transfers == 0
    assert itinerary.walk_seconds == 60
    assert itinerary.transport_modes == ("TRAM",)
    assert itinerary.boardings == 2
    assert itinerary.first_boarding_walk_m == 90


def test_transit_batch_is_resumed_only_when_its_value_count_matches(tmp_path: Path) -> None:
    path = tmp_path / "transit-0000.json"
    path.write_text('{"values":{"a":{},"b":{}}}')

    assert _valid_batch(path, 2)
    assert not _valid_batch(path, 3)


def test_transit_sample_batch_keeps_fastest_itinerary_details_and_parameters(tmp_path: Path) -> None:
    path = tmp_path / "transit-0000.parquet"
    _write_samples(
        path,
        {"a": [TransitSample("07:00", TransitItinerary(120, 1, 30, ("BUS", "RAIL"), 2, 125.5)), TransitSample("07:15", None)]},
        {"service_date": date(2026, 9, 2), "samples": ["07:00", "07:15"], "itinerary_detail_version": 2},
    )

    import pyarrow.parquet as pq

    assert not path.with_suffix(".partial.parquet").exists()
    assert pq.read_table(path).to_pylist() == [
        {"building_id": "a", "departure_time": "07:00", "state": "known", "duration_seconds": 120, "transfers": 1, "walk_seconds": 30, "transport_modes": ["BUS", "RAIL"], "boardings": 2, "first_boarding_walk_m": 125.5, "itinerary_start_time_ms": None, "itinerary_end_time_ms": None},
        {"building_id": "a", "departure_time": "07:15", "state": "unknown", "duration_seconds": None, "transfers": None, "walk_seconds": None, "transport_modes": None, "boardings": None, "first_boarding_walk_m": None, "itinerary_start_time_ms": None, "itinerary_end_time_ms": None},
    ]
    assert json.loads(pq.read_metadata(path).metadata[b"transit_parameters"]) == {"service_date": "2026-09-02", "samples": ["07:00", "07:15"], "itinerary_detail_version": 2}
    assert _valid_batch(path, 1, 2)


def test_transit_batch_is_recomputed_when_destination_parameters_change(tmp_path: Path) -> None:
    path = tmp_path / "transit-0000.parquet"
    _write_samples(
        path,
        {"a": [TransitSample("07:00", TransitItinerary(120, 1, 30))]},
        {"service_date": date(2026, 9, 2), "samples": ["07:00"], "destination": {"id": "keilaniemi", "latitude": 60.1712, "longitude": 24.8277}},
    )

    assert not _valid_batch(path, 1, 1, {"service_date": date(2026, 9, 2), "samples": ["07:00"], "destination": {"id": "keilaniemi", "latitude": 60.1771, "longitude": 24.8307}})


def test_transit_batch_reuses_existing_results_when_only_worker_count_changes(tmp_path: Path) -> None:
    path = tmp_path / "transit-0000.parquet"
    _write_samples(
        path,
        {"a": [TransitSample("07:00", TransitItinerary(120, 1, 30))]},
        {"service_date": date(2026, 9, 2), "samples": ["07:00"], "workers": 16, "destination": {"id": "tapiola", "latitude": 60.175, "longitude": 24.8052}},
    )

    assert _valid_batch(path, 1, 1, {"service_date": date(2026, 9, 2), "samples": ["07:00"], "workers": 1, "destination": {"id": "tapiola", "latitude": 60.175, "longitude": 24.8052}})
