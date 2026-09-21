from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from pipeline.sources.cycling_quality import (
    GOOD_STOPS_PER_KM,
    build_cycling_network,
    cycling_ease_score,
    assign_cycling_metrics,
    effective_minutes,
    measure_cycling_routes,
)

# A: 24.940/60.170, B: 24.942/60.170 (due east of A), C: 24.942/60.172 (due north
# of B), D: 24.944/60.170 (further east). Riding A -> B -> C therefore turns 90
# degrees at B.
NODES = (
    '<node id="1" lat="60.170" lon="24.940"/>'
    '<node id="2" lat="60.170" lon="24.942"/>'
    '<node id="3" lat="60.172" lon="24.942"/>'
    '<node id="4" lat="60.170" lon="24.944"/>'
)
SIGNAL_NODES = NODES.replace(
    '<node id="2" lat="60.170" lon="24.942"/>',
    '<node id="2" lat="60.170" lon="24.942"><tag k="highway" v="traffic_signals"/></node>',
)


def _write(path: Path, nodes: str, ways: str) -> Path:
    path.write_text(f'<osm version="0.6">{nodes}{ways}</osm>')
    return path


def _way(identifier: int, refs: tuple[int, ...], **tags: str) -> str:
    body = "".join(f'<nd ref="{ref}"/>' for ref in refs)
    body += '<tag k="highway" v="residential"/>' if "highway" not in tags else ""
    body += "".join(f'<tag k="{key}" v="{value}"/>' for key, value in tags.items())
    return f'<way id="{identifier}">{body}</way>'


def _index(network, osm_id: int) -> int:
    return network.nodes.index(osm_id)


def test_a_street_name_change_without_a_junction_is_not_a_turn(tmp_path: Path) -> None:
    # Two differently named streets meet at node 2, and the geometry bends 90
    # degrees there -- but node 2 is a pass-through (degree 2), so the rider never
    # had a choice and never had to remember anything.
    path = _write(
        tmp_path / "namechange.osm",
        NODES,
        _way(10, (1, 2), name="Aleksanterinkatu") + _way(11, (2, 3), name="Mannerheimintie"),
    )
    network = build_cycling_network(path)

    assert network.degree[_index(network, 2)] == 2
    indicators = measure_cycling_routes(network, Point(24.942, 60.172))
    assert indicators.turns[_index(network, 1)] == 0


def test_the_same_bend_counts_as_a_turn_at_a_real_junction(tmp_path: Path) -> None:
    # Identical geometry, but a third arm makes node 2 a junction: now the rider
    # has to know to turn there.
    path = _write(
        tmp_path / "junction.osm",
        NODES,
        _way(10, (1, 2), name="Aleksanterinkatu") + _way(11, (2, 3), name="Mannerheimintie") + _way(12, (2, 4)),
    )
    network = build_cycling_network(path)

    assert network.degree[_index(network, 2)] == 3
    indicators = measure_cycling_routes(network, Point(24.942, 60.172))
    assert indicators.turns[_index(network, 1)] == 1
    # Arriving at the destination itself involves no remembered turn.
    assert indicators.turns[_index(network, 3)] == 0


def test_going_straight_through_a_junction_is_not_a_turn(tmp_path: Path) -> None:
    # 1 -> 2 -> 4 runs due east through the junction at node 2.
    path = _write(
        tmp_path / "straight.osm",
        NODES,
        _way(10, (1, 2)) + _way(11, (2, 3)) + _way(12, (2, 4)),
    )
    network = build_cycling_network(path)

    indicators = measure_cycling_routes(network, Point(24.944, 60.170))
    assert network.degree[_index(network, 2)] == 3
    assert indicators.turns[_index(network, 1)] == 0


def test_traffic_signals_passed_on_the_way_are_counted_once(tmp_path: Path) -> None:
    path = _write(tmp_path / "signals.osm", SIGNAL_NODES, _way(10, (1, 2)) + _way(11, (2, 3)))
    network = build_cycling_network(path)

    indicators = measure_cycling_routes(network, Point(24.942, 60.172))
    # Node 1 rides through the signal at node 2; node 2 starts after it.
    assert indicators.stops[_index(network, 1)] == 1
    assert indicators.stops[_index(network, 2)] == 0


def test_rough_surface_and_pedestrian_mixing_count_as_slow_metres(tmp_path: Path) -> None:
    gravel = _write(tmp_path / "gravel.osm", NODES, _way(10, (1, 2), surface="gravel") + _way(11, (2, 3)))
    shared = _write(
        tmp_path / "shared.osm",
        NODES,
        f'<way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="cycleway"/><tag k="segregated" v="no"/></way>'
        + _way(11, (2, 3)),
    )
    smooth = _write(tmp_path / "smooth.osm", NODES, _way(10, (1, 2), surface="asphalt") + _way(11, (2, 3)))

    destination = Point(24.942, 60.172)
    gravel_slow = measure_cycling_routes(build_cycling_network(gravel), destination).slow_m[0]
    shared_slow = measure_cycling_routes(build_cycling_network(shared), destination).slow_m[0]
    smooth_slow = measure_cycling_routes(build_cycling_network(smooth), destination).slow_m[0]

    assert gravel_slow > 0 and shared_slow > 0
    # Untagged and asphalt surfaces are ridden at full speed.
    assert smooth_slow == 0


def test_ease_score_rewards_a_direct_uninterrupted_asphalt_ride() -> None:
    effortless = cycling_ease_score(route_m=5_000, straight_m=5_000, turns=1, stops=1, slow_m=0)
    interrupted = cycling_ease_score(route_m=5_000, straight_m=5_000, turns=1, stops=20, slow_m=0)
    twisty = cycling_ease_score(route_m=5_000, straight_m=5_000, turns=30, stops=1, slow_m=0)
    roundabout = cycling_ease_score(route_m=9_000, straight_m=5_000, turns=1, stops=1, slow_m=0)
    gravelly = cycling_ease_score(route_m=5_000, straight_m=5_000, turns=1, stops=1, slow_m=5_000)

    assert effortless == 100.0
    for worse in (interrupted, twisty, roundabout, gravelly):
        assert worse < effortless
    # A ride at the published "very good" stop rate still scores full marks.
    assert cycling_ease_score(5_000, 5_000, 1, GOOD_STOPS_PER_KM * 5, 0) == 100.0


def test_assign_cycling_ease_scores_buildings_and_marks_unreachable_unknown(tmp_path: Path) -> None:
    path = _write(tmp_path / "network.osm", NODES, _way(10, (1, 2)) + _way(11, (2, 3)))
    network = build_cycling_network(path)
    buildings = gpd.GeoDataFrame(
        {"building_id": ["near", "far"]},
        geometry=[Point(24.9401, 60.1701), Point(25.900, 61.900)],
        crs=4326,
    )

    values, minutes = assign_cycling_metrics(buildings, network, Point(24.942, 60.172))

    assert values["near"].state.value == "known"
    assert 0.0 <= values["near"].value <= 100.0
    # The distant building snaps to the same tiny network, so it is still scored;
    # what matters is that every building gets an explicit value.
    assert set(values) == {"near", "far"} and set(minutes) == {"near", "far"}
    assert minutes["near"].value > 0


def test_a_destination_snaps_into_the_main_component_not_a_nearby_island(tmp_path: Path) -> None:
    # Nodes 5-6 form a disconnected island sitting exactly on the query point, while
    # the real network (1-2-3) is a few metres further away. Snapping to the nearest
    # node would strand the whole destination -- as Myyrmaki did on the real extract,
    # where it landed on a 26-node island 5 m away and scored 1 building out of 106k.
    nodes = NODES + '<node id="5" lat="60.17205" lon="24.9421"/><node id="6" lat="60.17205" lon="24.9422"/>'
    path = _write(tmp_path / "island.osm", nodes, _way(10, (1, 2)) + _way(11, (2, 3)) + _way(13, (5, 6)))
    network = build_cycling_network(path)

    assert not network.main_component[_index(network, 5)]
    indicators = measure_cycling_routes(network, Point(24.9421, 60.17205))
    # The far end of the real network is still reachable.
    assert indicators.route_m[_index(network, 1)] < float("inf")


def test_a_short_ride_is_not_punished_by_per_kilometre_rates() -> None:
    # One light 300 m from the door is not "3.3 stops/km" of misery.
    assert cycling_ease_score(route_m=300, straight_m=300, turns=1, stops=1, slow_m=0) > 80


def test_a_bike_legal_footway_is_rideable_but_counts_as_slow(tmp_path: Path) -> None:
    # Excluding pedestrianised streets made Kamppi -> Central Station route 1.70 km
    # instead of ~1.1 km. They are rideable where cycling is signed, but shared.
    allowed = _write(
        tmp_path / "allowed.osm", NODES,
        '<way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="pedestrian"/><tag k="bicycle" v="yes"/></way>'
        + _way(11, (2, 3)),
    )
    forbidden = _write(
        tmp_path / "forbidden.osm", NODES,
        '<way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="footway"/></way>' + _way(11, (2, 3)),
    )
    destination = Point(24.942, 60.172)

    network = build_cycling_network(allowed)
    indicators = measure_cycling_routes(network, destination)
    assert indicators.route_m[_index(network, 1)] < float("inf")
    assert indicators.slow_m[_index(network, 1)] > 0  # shared with pedestrians

    # A plain footway with no cycling permission stays out of the graph.
    assert 1 not in build_cycling_network(forbidden).nodes
