"""Route-measured cycling ease, following the CROW / Fietsbalans quality criteria.

The Dutch CROW *Design Manual for Bicycle Traffic* defines five requirements for a
cycle network; two of them describe what makes a ride feel easy:

* **Directness** -- a short route with minimal *delay* (time lost stopping).
* **Comfort** -- "minimisation of energy expenditure *and mental concentration*".

The Fietsbalans method operationalises those into measurable route indicators, and
the data-driven assessment in Frontiers in Future Transportation (2023) shows they
can be derived from OpenStreetMap. This module follows that approach: it does not
invent a routing cost model, it **measures the route the cyclist actually rides**
and grades the result against the published thresholds.

Three complaints, three measured indicators:

===========================  ==========================  =========================
Complaint                    Indicator                   "Very good" threshold
===========================  ==========================  =========================
"where do I turn again?"     turns per km, detour factor detour < 1.2
"traffic light again"        stops per km                < 0.75 stops/km
"I cannot ride fast here"    slow-surface / mixing share paved and segregated
===========================  ==========================  =========================

Deliberately **not** modelled: who has priority at an unsignalised crossing (OSM
``give_way`` is too sparsely mapped to infer reliably) and switching to the other
side of the road (not derivable). Guessing either would make the score unjustifiable.

A turn is only counted at a **junction** -- a node where the rider actually has a
choice (graph degree >= 3) *and* the heading changes. A street name change, a way
split, or road curvature at a pass-through node is never a turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import osmium
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import Point

from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState

# Ways a bicycle may ride on. Mirrors the cycling set used by the routing graph.
CYCLING_HIGHWAYS = frozenset({
    "cycleway", "path", "residential", "living_street", "service",
    "tertiary", "secondary", "primary", "unclassified", "track",
})

# Pedestrian streets and footways are rideable only where cycling is explicitly
# allowed, and they are always shared with people on foot. Leaving them out
# inflated inner-city routes badly: Kamppi -> Central Station came out as 1.70 km
# (detour factor 2.6) instead of the real ~1.1 km, because the direct connections
# through the pedestrianised core were invisible. Suburban routes barely move.
SHARED_HIGHWAYS = frozenset({"footway", "pedestrian"})
RIDEABLE_SHARED = frozenset({"yes", "designated"})

# Surfaces that force you to slow down. Anything untagged is assumed rideable:
# OSM surface coverage is partial, so only an *explicit* slow surface is penalised.
SLOW_SURFACES = frozenset({
    "gravel", "fine_gravel", "ground", "dirt", "earth", "grass", "sand", "mud",
    "wood", "pebblestone", "unpaved", "cobblestone", "sett", "compacted",
})

# A heading change at a junction below this is a bend in the road, not a decision.
TURN_DEGREES = 40.0
# Direction changes closer together than this are one manoeuvre, not several.
# Calibrated against BRouter's turn-by-turn instructions over 33 routes spanning
# 2-12 km: this detector runs at 3.73 turns/km against BRouter's 2.84 (|angle| >=
# 40 deg), i.e. 1.20x, with a p10-p90 spread of 0.82-1.68x and never a zero. A
# smoothed variant that compared headings over a 25 m window scored better on
# average (1.11x) but was far less reliable (0.44-2.25x, and it missed every turn
# on one 1.9 km route that had 61 junctions), because a corner straddling a window
# boundary averages away. Consistency matters more than the last 9% here.
TURN_MERGE_M = 25.0

# Published "very good" thresholds (CROW / Fietsbalans / Frontiers 2023).
GOOD_DETOUR_FACTOR = 1.2
POOR_DETOUR_FACTOR = 1.6
# Fietsersbond (2008) braking-frequency scale: <0.75 very good ... >1.65 very poor.
GOOD_STOPS_PER_KM = 0.75
POOR_STOPS_PER_KM = 1.65
# Turns per km has no published threshold; this in-house scale is the one judgement
# call in the model and is kept explicit so it can be tuned.
GOOD_TURNS_PER_KM = 1.0
POOR_TURNS_PER_KM = 5.0

# Weights across the three complaints. Stops are weighted highest because they are
# the best-evidenced indicator and rest on authoritative data.
WEIGHT_STOPS = 0.35
WEIGHT_TURNS = 0.25
WEIGHT_DETOUR = 0.20
WEIGHT_COMFORT = 0.20

# --- Generalized ("effective") travel time -----------------------------------
# Seconds lost per signal stop.
#
# The two Fietsersbond (2008) scales must agree, so dividing delay by braking
# frequency at each matching grade boundary implies the cost of one forced stop:
# 16/0.75 = 21 s (very good), 26/1.05 = 25 s, 36/1.35 = 27 s, 46/1.65 = 28 s. But
# braking frequency counts *intersections without right-of-way* -- every forced
# stop, yields included -- and a yield is far cheaper than a red light, so the
# signal-only figure has to sit above that 21-28 s blend.
#
# Ordinary traffic engineering agrees: a random arrival waits C(1-g)^2/2, which at
# Helsinki cycle lengths (90-120 s, cyclist green share ~0.3) is 20-30 s, plus the
# 5-8 s a cyclist loses decelerating and re-accelerating. Two-stage crossings of
# wide arterials cost more again. 30 s is the defensible central value; 20 s was
# too low because it came from the "very good" boundary of an ideal network.
SIGNAL_DELAY_S = 30.0
# Seconds lost per turn. Valhalla's default `maneuver_penalty` is 5 s, but that is a
# generic road-change cost. A cyclist turning at a junction scrubs speed from ~15 to
# ~8 km/h and rebuilds it, which alone costs about 5 s, and on top of that has to
# recognise the junction and check for people and traffic before committing. 10 s is
# the defensible cyclist figure, and it matters more now that turns are counted
# properly: the windowed measurement leaves far fewer, but each is a real manoeuvre.
TURN_PENALTY_S = 10.0
# Crossing a road or driveway with no lights: you scrub speed and check, but rarely
# stop outright. This is CROW's "conflict point" / "intersection without
# right-of-way" -- the HSL extract tags ~36,600 unsignalised crossings.
# Measured at 5 s this was far too heavy: central routes carry ~11 tagged crossings
# per km (CROW calls >6/km "very poor"), because OSM tags a crossing per carriageway
# and marks every minor side street, and it dragged city speeds down to 8-9 km/h
# against a real 12-15. Most of these cost a glance, not a brake.
CROSSING_DELAY_S = 2.0
# Riding a rough or pedestrian-shared stretch costs speed rather than a fixed delay.
SLOW_SPEED_FACTOR = 0.65


@dataclass(frozen=True)
class CyclingNetwork:
    """Cycling graph enriched with the attributes the ease indicators need."""

    nodes: list[int]
    coordinates: np.ndarray
    graph: csr_matrix
    degree: np.ndarray
    signal: np.ndarray
    crossing: np.ndarray
    edge_key: np.ndarray
    edge_length: np.ndarray
    edge_slow: np.ndarray
    # The OSM cycling graph breaks into thousands of components (the HSL extract has
    # ~4,000, the largest holding 85% of nodes). A destination must snap into the
    # main one: snapping Myyrmaki to a 26-node island 5 m away silently left the
    # whole layer unreachable.
    main_component: np.ndarray


@dataclass(frozen=True)
class RouteIndicators:
    """Per-node cumulative measurements of the ride towards one destination.

    ``cost_s`` is the generalized (perceived) travel time the route was chosen to
    minimise: riding time at a surface-adjusted speed plus signal delay. Turn
    penalties are added afterwards, from ``turns``.
    """

    route_m: np.ndarray
    turns: np.ndarray
    stops: np.ndarray
    crossings: np.ndarray
    slow_m: np.ndarray
    cost_s: np.ndarray


class _CyclingQualityHandler(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self.edges: list[tuple[int, int, bool]] = []
        self.coordinates: dict[int, tuple[float, float]] = {}
        self.signals: set[int] = set()
        self.crossings: set[int] = set()

    def node(self, node: osmium.osm.Node) -> None:
        self.coordinates[node.id] = (node.location.lon, node.location.lat)
        if _is_signal(node.tags):
            self.signals.add(node.id)
        elif node.tags.get("highway") == "crossing":
            self.crossings.add(node.id)

    def way(self, way: osmium.osm.Way) -> None:
        highway = way.tags.get("highway")
        bicycle = way.tags.get("bicycle")
        rideable = highway in CYCLING_HIGHWAYS and bicycle != "no"
        shared = highway in SHARED_HIGHWAYS and bicycle in RIDEABLE_SHARED
        if not (rideable or shared):
            return
        # Riding among pedestrians is always slow, whatever the surface says.
        slow = shared or _is_slow(way.tags, highway)
        references = [node.ref for node in way.nodes]
        self.edges.extend((start, end, slow) for start, end in zip(references, references[1:]))


def _is_signal(tags: osmium.osm.TagList) -> bool:
    """A node where the rider has to stop for a light.

    Counting only ``highway=traffic_signals`` misses most cyclist stops: in the HSL
    extract that tag covers 3,534 nodes, while a further 4,771 signalised
    *crossings* -- the ones a rider on a cycleway actually meets -- are tagged
    ``highway=crossing`` with ``crossing=traffic_signals``/``crossing:signals=yes``.
    """
    if tags.get("highway") == "traffic_signals":
        return True
    return tags.get("highway") == "crossing" and (
        tags.get("crossing") == "traffic_signals" or tags.get("crossing:signals") == "yes"
    )


def _is_slow(tags: osmium.osm.TagList, highway: str) -> bool:
    """A stretch you cannot ride at normal speed: rough surface, or shared with pedestrians."""
    if tags.get("surface") in SLOW_SURFACES:
        return True
    segregated = tags.get("segregated")
    if segregated == "no":
        return True
    return highway == "path" and segregated is None and tags.get("foot") != "no"


def build_cycling_network(path: Path) -> CyclingNetwork:
    handler = _CyclingQualityHandler()
    handler.apply_file(str(path), locations=True)
    nodes = sorted({node for start, end, _ in handler.edges for node in (start, end) if node in handler.coordinates})
    positions = {node: index for index, node in enumerate(nodes)}
    count = len(nodes)
    coordinates = np.array([handler.coordinates[node] for node in nodes], dtype=float).reshape(count, 2)

    keys: dict[int, tuple[float, bool]] = {}
    neighbours: dict[int, set[int]] = {}
    for start, end, slow in handler.edges:
        if start not in positions or end not in positions or start == end:
            continue
        first, second = positions[start], positions[end]
        low, high = (first, second) if first < second else (second, first)
        key = low * count + high
        length = _distance_m(handler.coordinates[start], handler.coordinates[end])
        previous = keys.get(key)
        # A stretch mapped twice keeps the pessimistic (slow) reading.
        keys[key] = (length, slow or previous[1]) if previous else (length, slow)
        neighbours.setdefault(low, set()).add(high)
        neighbours.setdefault(high, set()).add(low)

    edge_key = np.array(sorted(keys), dtype=np.int64)
    edge_length = np.array([keys[int(key)][0] for key in edge_key], dtype=float)
    edge_slow = np.array([keys[int(key)][1] for key in edge_key], dtype=bool)
    degree = np.zeros(count, dtype=np.int32)
    for index, connected in neighbours.items():
        degree[index] = len(connected)

    rows = (edge_key // count).astype(np.int64)
    columns = (edge_key % count).astype(np.int64)
    graph = csr_matrix(
        (np.concatenate([edge_length, edge_length]), (np.concatenate([rows, columns]), np.concatenate([columns, rows]))),
        shape=(count, count),
    )
    signal = np.array([node in handler.signals for node in nodes], dtype=bool)
    crossing = np.array([node in handler.crossings for node in nodes], dtype=bool)
    if count:
        labels = connected_components(graph, directed=False)[1]
        main_component = labels == np.bincount(labels).argmax()
    else:
        main_component = np.zeros(0, dtype=bool)
    return CyclingNetwork(nodes, coordinates, graph, degree, signal, crossing, edge_key, edge_length, edge_slow, main_component)


def _distance_m(start: tuple[float, float], end: tuple[float, float]) -> float:
    mean_latitude = np.radians((start[1] + end[1]) / 2)
    east = (end[0] - start[0]) * np.cos(mean_latitude) * 111_320
    north = (end[1] - start[1]) * 110_540
    return float(np.hypot(east, north))


def _bearings(coordinates: np.ndarray, origin: np.ndarray, target: np.ndarray) -> np.ndarray:
    start, end = coordinates[origin], coordinates[target]
    mean_latitude = np.radians((start[:, 1] + end[:, 1]) / 2)
    east = (end[:, 0] - start[:, 0]) * np.cos(mean_latitude)
    north = end[:, 1] - start[:, 1]
    return np.degrees(np.arctan2(east, north))


def turn_flags(network: CyclingNetwork, predecessors: np.ndarray) -> np.ndarray:
    """True where riding ``node -> parent -> grandparent`` turns at a real junction.

    The turn happens *at the parent*, so it only counts when the parent is a
    junction the rider could have chosen differently (degree >= 3). Pass-through
    nodes -- a street-name change, a way split, or a curve -- are never turns.
    """
    count = len(network.nodes)
    parent = predecessors
    has_parent = parent >= 0
    grandparent = np.full(count, -1, dtype=np.int64)
    grandparent[has_parent] = parent[parent[has_parent]]
    turning = has_parent & (grandparent >= 0)
    flags = np.zeros(count, dtype=bool)
    if not turning.any():
        return flags
    nodes = np.nonzero(turning)[0]
    incoming = _bearings(network.coordinates, nodes, parent[nodes])
    outgoing = _bearings(network.coordinates, parent[nodes], grandparent[nodes])
    change = np.abs((outgoing - incoming + 180.0) % 360.0 - 180.0)
    flags[nodes] = (change >= TURN_DEGREES) & (network.degree[parent[nodes]] >= 3)
    return flags


def _edge_attributes(network: CyclingNetwork, first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    count = len(network.nodes)
    low = np.minimum(first, second).astype(np.int64)
    high = np.maximum(first, second).astype(np.int64)
    position = np.searchsorted(network.edge_key, low * count + high)
    position = np.clip(position, 0, max(len(network.edge_key) - 1, 0))
    found = len(network.edge_key) > 0
    return (network.edge_length[position], network.edge_slow[position]) if found else (np.zeros(len(first)), np.zeros(len(first), dtype=bool))


def build_cost_graph(network: CyclingNetwork, speed_kmh: float) -> csr_matrix:
    """Edge weights in seconds of perceived time, so routing avoids friction.

    Riding time uses a reduced speed on rough or pedestrian-shared stretches. A
    signal's delay is split half onto each edge touching it, so any route passing
    *through* the node pays the full delay while the graph stays symmetric -- that
    keeps signals in the routing cost without expanding the graph.
    """
    metres_per_second = speed_kmh * 1_000 / 3_600
    seconds = network.edge_length / np.where(network.edge_slow, metres_per_second * SLOW_SPEED_FACTOR, metres_per_second)
    count = len(network.nodes)
    rows = (network.edge_key // count).astype(np.int64)
    columns = (network.edge_key % count).astype(np.int64)
    node_delay = SIGNAL_DELAY_S * network.signal.astype(float) + CROSSING_DELAY_S * network.crossing.astype(float)
    seconds = seconds + 0.5 * (node_delay[rows] + node_delay[columns])
    return csr_matrix(
        (np.concatenate([seconds, seconds]), (np.concatenate([rows, columns]), np.concatenate([columns, rows]))),
        shape=(count, count),
    )


def measure_cycling_routes(network: CyclingNetwork, destination: Point, speed_kmh: float = 15.0) -> RouteIndicators:
    """Measure every node's ride to ``destination`` on the least-friction route.

    Routing minimises perceived seconds (riding time + signal delay + slow surface),
    so the measured route is the one a rider would plausibly choose rather than the
    bare shortest line. One Dijkstra rooted at the destination yields a predecessor
    tree; walking it outwards accumulates each node's distance, turns, stops and
    slow metres in a single pass.
    """
    count = len(network.nodes)
    empty = np.full(count, np.inf)
    if not count:
        return RouteIndicators(empty, empty, empty, empty, empty, empty)
    # Snap the destination into the main component, never onto a nearby island.
    reachable_nodes = np.nonzero(network.main_component)[0]
    if not len(reachable_nodes):
        return RouteIndicators(empty, empty, empty, empty, empty, empty)
    tree = cKDTree(network.coordinates[reachable_nodes])
    root = int(reachable_nodes[tree.query([(destination.x, destination.y)])[1][0]])
    cost, predecessors = dijkstra(build_cost_graph(network, speed_kmh), directed=False, indices=root, return_predecessors=True)
    predecessors = predecessors.astype(np.int64)

    reachable = np.isfinite(cost)
    order = np.argsort(cost, kind="stable")
    metres = np.zeros(count)
    turns = np.zeros(count)
    stops = np.zeros(count)
    crossings = np.zeros(count)
    slow = np.zeros(count)
    lengths, slow_edge = _edge_attributes(network, np.arange(count), np.maximum(predecessors, 0))
    flags = turn_flags(network, predecessors)

    last_turn_m = np.zeros(count)
    for node in order:
        parent = predecessors[node]
        if parent < 0 or not reachable[node]:
            continue
        metres[node] = metres[parent] + lengths[node]
        stops[node] = stops[parent] + (1.0 if network.signal[parent] else 0.0)
        crossings[node] = crossings[parent] + (1.0 if network.crossing[parent] else 0.0)
        slow[node] = slow[parent] + (lengths[node] if slow_edge[node] else 0.0)
        # Direction changes within one manoeuvre of each other are a single corner.
        counted = flags[node] and metres[node] - last_turn_m[parent] >= TURN_MERGE_M
        turns[node] = turns[parent] + (1.0 if counted else 0.0)
        last_turn_m[node] = metres[node] if counted else last_turn_m[parent]

    return RouteIndicators(
        np.where(reachable, metres, np.inf),
        np.where(reachable, turns, np.inf),
        np.where(reachable, stops, np.inf),
        np.where(reachable, crossings, np.inf),
        np.where(reachable, slow, np.inf),
        np.where(reachable, cost, np.inf),
    )


def effective_minutes(cost_s: float, turns: float) -> float:
    """Perceived door-to-door cycling time: routed cost plus the turn penalties."""
    return round((cost_s + TURN_PENALTY_S * turns) / 60.0, 1)


def _sub_score(value: float, good: float, poor: float) -> float:
    """1.0 at or better than the published "very good" threshold, 0.0 at "poor"."""
    if value <= good:
        return 1.0
    if value >= poor:
        return 0.0
    return float((poor - value) / (poor - good))


def cycling_ease_score(route_m: float, straight_m: float, turns: float, stops: float, slow_m: float) -> float:
    """Combine the measured indicators into a 0-100 ease score (100 = effortless)."""
    # Per-kilometre rates are meaningless on a very short ride -- one light 300 m
    # from the door is not "3.3 stops/km" of misery -- so the denominator floors at 1 km.
    kilometres = max(route_m / 1_000.0, 1.0)
    detour = route_m / straight_m if straight_m > 0 else 1.0
    comfort = 1.0 - min(slow_m / route_m, 1.0) if route_m > 0 else 1.0
    score = (
        WEIGHT_STOPS * _sub_score(stops / kilometres, GOOD_STOPS_PER_KM, POOR_STOPS_PER_KM)
        + WEIGHT_TURNS * _sub_score(turns / kilometres, GOOD_TURNS_PER_KM, POOR_TURNS_PER_KM)
        + WEIGHT_DETOUR * _sub_score(detour, GOOD_DETOUR_FACTOR, POOR_DETOUR_FACTOR)
        + WEIGHT_COMFORT * comfort
    )
    return round(100.0 * score, 1)


def assign_cycling_metrics(
    buildings, network: CyclingNetwork, destination: Point, speed_kmh: float = 15.0,
) -> tuple[dict[str, BuildingValue], dict[str, BuildingValue]]:
    """Score every building's ride to ``destination``: (ease 0-100, effective minutes).

    Both come from one routing pass, so adding the second metric costs nothing.
    """
    identifiers = list(buildings["building_id"])
    unknown = BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, coverage=0, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
    if not len(network.nodes):
        return ({identifier: unknown for identifier in identifiers},) * 2

    indicators = measure_cycling_routes(network, destination, speed_kmh)
    points = buildings.to_crs(4326).geometry.representative_point()
    longitudes = np.array([point.x if point is not None else np.nan for point in points], dtype=float)
    latitudes = np.array([point.y if point is not None else np.nan for point in points], dtype=float)
    usable = np.isfinite(longitudes) & np.isfinite(latitudes)
    indices = np.full(len(identifiers), -1, dtype=np.int64)
    if usable.any():
        indices[usable] = cKDTree(network.coordinates).query(np.column_stack([longitudes[usable], latitudes[usable]]))[1]

    ease: dict[str, BuildingValue] = {}
    minutes: dict[str, BuildingValue] = {}
    for position, identifier in enumerate(identifiers):
        index = int(indices[position])
        route_m = indicators.route_m[index] if index >= 0 else np.inf
        if index < 0 or not np.isfinite(route_m) or route_m <= 0:
            ease[identifier] = minutes[identifier] = unknown
            continue
        turns, stops = float(indicators.turns[index]), float(indicators.stops[index])
        straight_m = _distance_m((longitudes[position], latitudes[position]), (destination.x, destination.y))
        ease[identifier] = BuildingValue(
            ValueState.KNOWN, ValueKind.SCALAR,
            cycling_ease_score(float(route_m), straight_m, turns, stops, float(indicators.slow_m[index])),
            coverage=1, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM,
        )
        minutes[identifier] = BuildingValue(
            ValueState.KNOWN, ValueKind.SCALAR, effective_minutes(float(indicators.cost_s[index]), turns),
            coverage=1, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM,
        )
    return ease, minutes
