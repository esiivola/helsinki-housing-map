from __future__ import annotations

from pathlib import Path
from math import asin, cos, radians, sin, sqrt

import geopandas as gpd
import networkx as nx
import numpy as np
import osmium
from scipy.sparse import csr_matrix, hstack, vstack
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState
from shapely.geometry import LineString, Point, Polygon, mapping


GROCERY_STORE_GROUPS = (
    "prisma", "k_citymarket", "lidl", "s_market", "k_supermarket", "sale",
    "k_market", "alepa", "other_supermarket", "other_grocery",
)
HEALTH_PROVIDER_GROUPS = ("mehilainen", "terveystalo", "pihlajalinna")
PRISMA_TRIPLA = Point(24.92991, 60.19846)
# Destination source points can be inside shopping centres or institutional
# parcels, while the nearest pedestrian way is outside the parcel boundary.
# The routing value always includes this access leg, so include nearby
# alternatives far enough to avoid selecting an isolated service edge.
DESTINATION_ACCESS_RADIUS_M = 150


class _DestinationHandler(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self.grocery: list[Point] = []
        self.supermarket: list[Point] = []
        self.grocery_store: dict[str, list[tuple[Point, str]]] = {group: [] for group in GROCERY_STORE_GROUPS}
        self.daycare: list[tuple[Point, str]] = []
        self.school: list[tuple[Point, str]] = []
        self.healthcare: list[tuple[Point, str]] = []
        self.health_provider: dict[str, list[tuple[Point, str]]] = {group: [] for group in HEALTH_PROVIDER_GROUPS}
        self.library: list[tuple[Point, str]] = []
        self.forest: list[Polygon] = []
        self.shore: list[Point] = []

    def node(self, node: osmium.osm.Node) -> None:
        point = Point(node.location.lon, node.location.lat)
        self._add_shop(node.tags, point)
        self._add_amenity(node.tags, point)

    def area(self, area: osmium.osm.Area) -> None:
        try:
            ring = [(node.lon, node.lat) for node in next(iter(area.outer_rings()))]
        except (IndexError, StopIteration, osmium.InvalidLocationError):
            return
        polygon = Polygon(ring)
        self._add_shop(area.tags, polygon.representative_point())
        if area.tags.get("natural") == "wood" or area.tags.get("landuse") == "forest":
            self.forest.append(polygon)
        self._add_amenity(area.tags, polygon.representative_point())

    def way(self, way: osmium.osm.Way) -> None:
        try:
            points = [Point(node.lon, node.lat) for node in way.nodes]
        except osmium.InvalidLocationError:
            return
        if way.tags.get("amenity") and points:
            self._add_amenity(way.tags, LineString(points).representative_point())
        if way.tags.get("natural") == "coastline":
            self.shore.extend(points)

    def _add_amenity(self, tags: osmium.osm.TagList, point: Point) -> None:
        amenity = tags.get("amenity")
        if amenity in {"kindergarten", "childcare"}:
            self.daycare.append((point, _destination_name(tags, "Päiväkoti")))
        elif amenity == "school":
            self.school.append((point, _destination_name(tags, "Koulu")))
        elif amenity in {"clinic", "doctors", "hospital"} or tags.get("healthcare") in {"clinic", "doctor", "hospital"}:
            self.healthcare.append((point, _destination_name(tags, "Terveyspalvelu")))
            label = " ".join(filter(None, (tags.get("brand"), tags.get("name"), tags.get("operator")))).casefold()
            group = "mehilainen" if "mehiläinen" in label else "terveystalo" if "terveystalo" in label else "pihlajalinna" if "pihlajalinna" in label else None
            if group is not None:
                self.health_provider[group].append((point, _destination_name(tags, group.title())))
        elif amenity == "library":
            self.library.append((point, _destination_name(tags, "Kirjasto")))

    def _add_shop(self, tags: osmium.osm.TagList, point: Point) -> None:
        shop = tags.get("shop")
        if shop not in {"supermarket", "convenience", "grocery"}:
            return
        self.grocery.append(point)
        if shop == "supermarket":
            self.supermarket.append(point)
        label = (tags.get("brand") or tags.get("name") or "").casefold()
        group = (
            "prisma" if label.startswith("prisma") else "k_citymarket" if label.startswith("k-citymarket")
            else "lidl" if label.startswith("lidl") else "k_supermarket" if label.startswith("k-supermarket")
            else "s_market" if label.startswith("s-market") else "sale" if label.startswith("sale")
            else "k_market" if label.startswith("k-market") else "alepa" if label.startswith("alepa")
            else "other_supermarket" if shop == "supermarket" else "other_grocery"
        )
        self.grocery_store[group].append((point, _destination_name(tags, group.replace("_", " ").title())))


class _PedestrianHandler(osmium.SimpleHandler):
    def __init__(self, cycling: bool = False) -> None:
        super().__init__()
        self.cycling = cycling
        self.edges: list[tuple[int, int]] = []
        self.coordinates: dict[int, tuple[float, float]] = {}

    def node(self, node: osmium.osm.Node) -> None:
        self.coordinates[node.id] = (node.location.lon, node.location.lat)

    def way(self, way: osmium.osm.Way) -> None:
        allowed = {"cycleway", "path", "residential", "living_street", "service", "tertiary", "secondary", "primary", "unclassified", "track"} if self.cycling else {"footway", "path", "pedestrian", "residential", "living_street", "service", "tertiary", "secondary", "primary", "unclassified", "track", "cycleway"}
        if way.tags.get("highway") not in allowed or (way.tags.get("bicycle") == "no" if self.cycling else way.tags.get("foot") == "no"):
            return
        nodes = [node.ref for node in way.nodes]
        self.edges.extend(zip(nodes, nodes[1:]))


class _BasemapHandler(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self.features: list[dict[str, object]] = []

    def way(self, way: osmium.osm.Way) -> None:
        kind = (
            "road-major" if way.tags.get("highway") in {"motorway", "trunk", "primary", "secondary", "tertiary"}
            else "rail" if way.tags.get("railway") in {"rail", "light_rail", "subway"}
            else "waterway" if way.tags.get("waterway") in {"river", "canal"}
            else "coastline" if way.tags.get("natural") == "coastline"
            else None
        )
        if kind is None:
            return
        try:
            geometry = LineString([(node.lon, node.lat) for node in way.nodes])
        except osmium.InvalidLocationError:
            return
        if geometry.is_empty or len(geometry.coords) < 2:
            return
        self.features.append(_basemap_feature(kind, geometry))

    def area(self, area: osmium.osm.Area) -> None:
        kind = "water" if area.tags.get("natural") == "water" or area.tags.get("water") else "green" if area.tags.get("leisure") == "park" or area.tags.get("natural") == "wood" or area.tags.get("landuse") == "forest" else None
        if kind is None:
            return
        try:
            geometry = Polygon([(node.lon, node.lat) for node in next(iter(area.outer_rings()))])
        except (IndexError, osmium.InvalidLocationError):
            return
        if geometry.is_empty or not geometry.is_valid:
            return
        self.features.append(_basemap_feature(kind, geometry))


def extract_destinations(path: Path) -> dict[str, gpd.GeoDataFrame]:
    handler = _DestinationHandler()
    handler.apply_file(str(path), locations=True)
    destinations = {
        "grocery": gpd.GeoDataFrame(geometry=handler.grocery, crs=4326),
        "supermarket": gpd.GeoDataFrame(geometry=handler.supermarket, crs=4326),
        **{f"grocery_store_{group}": _named_points(points) for group, points in handler.grocery_store.items()},
        "daycare": _named_points(handler.daycare),
        "school": _named_points(handler.school),
        "healthcare": _named_points(handler.healthcare),
        **{f"health_provider_{group}": _named_points(points) for group, points in handler.health_provider.items()},
        "library": _named_points(handler.library),
        "forest": gpd.GeoDataFrame(geometry=handler.forest, crs=4326),
        "shore": gpd.GeoDataFrame(geometry=handler.shore, crs=4326),
    }
    # OSM node 6888009532 (Prisma Tripla) is missing from the 2026-08-25 routing
    # snapshot. Keep this known Prisma destination in the same input used for
    # route distances until the snapshot includes a point within roughly 30 m.
    prisma = destinations["grocery_store_prisma"]
    if not any(point.distance(PRISMA_TRIPLA) < 0.0003 for point in prisma.geometry):
        destinations["grocery_store_prisma"] = gpd.GeoDataFrame({"name": [*prisma["name"], "Prisma Tripla"]}, geometry=[*prisma.geometry, PRISMA_TRIPLA], crs=4326)
    return destinations


def _named_points(points: list[tuple[Point, str]]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"name": [name for _, name in points]}, geometry=[point for point, _ in points], crs=4326)


def _destination_name(tags: osmium.osm.TagList, fallback: str) -> str:
    return tags.get("name") or tags.get("brand") or tags.get("operator") or fallback


def extract_basemap(path: Path) -> dict[str, object]:
    handler = _BasemapHandler()
    handler.apply_file(str(path), locations=True)
    return {"type": "FeatureCollection", "features": handler.features}


def _basemap_feature(kind: str, geometry: LineString | Polygon) -> dict[str, object]:
    return {"type": "Feature", "properties": {"kind": kind}, "geometry": mapping(geometry)}


def extract_pedestrian_edges(path: Path) -> list[tuple[int, int]]:
    handler = _PedestrianHandler()
    handler.apply_file(str(path))
    return handler.edges


def extract_pedestrian_graph(path: Path) -> nx.DiGraph:
    handler = _PedestrianHandler()
    handler.apply_file(str(path), locations=True)
    graph = nx.DiGraph()
    for start, end in handler.edges:
        if start not in handler.coordinates or end not in handler.coordinates:
            continue
        length_m = _distance_m(handler.coordinates[start], handler.coordinates[end])
        graph.add_node(start, coordinate=handler.coordinates[start])
        graph.add_node(end, coordinate=handler.coordinates[end])
        graph.add_edge(start, end, length_m=length_m)
        graph.add_edge(end, start, length_m=length_m)
    return graph


def extract_pedestrian_sparse_graph(path: Path) -> tuple[list[int], np.ndarray, csr_matrix]:
    handler = _PedestrianHandler()
    return _sparse_graph(handler, path)


def extract_cycling_sparse_graph(path: Path) -> tuple[list[int], np.ndarray, csr_matrix]:
    return _sparse_graph(_PedestrianHandler(cycling=True), path)


def _sparse_graph(handler: _PedestrianHandler, path: Path) -> tuple[list[int], np.ndarray, csr_matrix]:
    handler.apply_file(str(path), locations=True)
    nodes = sorted({node for edge in handler.edges for node in edge if node in handler.coordinates})
    positions = {node: index for index, node in enumerate(nodes)}
    rows: list[int] = []
    columns: list[int] = []
    weights: list[float] = []
    for start, end in handler.edges:
        if start not in positions or end not in positions:
            continue
        distance = _distance_m(handler.coordinates[start], handler.coordinates[end])
        rows.extend((positions[start], positions[end]))
        columns.extend((positions[end], positions[start]))
        weights.extend((distance, distance))
    return nodes, np.array([handler.coordinates[node] for node in nodes]), csr_matrix((weights, (rows, columns)), shape=(len(nodes), len(nodes)))


def sparse_destination_distances(graph: csr_matrix, nodes: list[int], destination_nodes: list[int]) -> np.ndarray:
    positions = {node: index for index, node in enumerate(nodes)}
    return _sparse_destination_access_distances(graph, {positions[node]: 0 for node in destination_nodes})


def _sparse_destination_access_distances(graph: csr_matrix, destination_access: dict[int, float]) -> np.ndarray:
    destinations = list(destination_access)
    super_source = csr_matrix((list(destination_access.values()), (np.zeros(len(destinations)), destinations)), shape=(1, graph.shape[0]))
    expanded = vstack((hstack((graph, csr_matrix((graph.shape[0], 1)))), hstack((super_source, csr_matrix((1, 1)))))).tocsr()
    return dijkstra(expanded, directed=True, indices=graph.shape[0])[:-1]


def assign_sparse_route_distances(
    buildings: gpd.GeoDataFrame,
    nodes: list[int],
    coordinates: np.ndarray,
    graph: csr_matrix,
    destinations: list[Point | Polygon],
) -> dict[str, BuildingValue]:
    if not destinations:
        return {
            building_id: BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
            for building_id in buildings["building_id"]
        }
    tree = cKDTree(coordinates)
    destination_points = [point if isinstance(point, Point) else point.representative_point() for point in destinations]
    access_nodes = _destination_access_nodes(tree, coordinates, destination_points)
    distances = _sparse_destination_access_distances(graph, access_nodes)
    geometries = buildings.to_crs(4326).geometry
    valid = [
        geometry is not None and not geometry.is_empty and geometry.is_valid
        for geometry in geometries
    ]
    points = [
        geometry.representative_point() if is_valid else None
        for geometry, is_valid in zip(geometries, valid, strict=True)
    ]
    building_indices = np.full(len(points), -1)
    if any(valid):
        _, building_indices[np.array(valid)] = tree.query([(point.x, point.y) for point, is_valid in zip(points, valid, strict=True) if is_valid])
    values = {}
    for building_id, index, point in zip(buildings["building_id"], building_indices, points, strict=True):
        value = _building_access_distance(point, index, tree, coordinates, distances)
        values[building_id] = BuildingValue(
            ValueState.KNOWN if value is not None else ValueState.UNKNOWN,
            ValueKind.SCALAR, value, coverage=1 if value is not None else 0,
            method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM,
        )
    return values


def _destination_access_nodes(tree: cKDTree, coordinates: np.ndarray, destinations: list[Point]) -> dict[int, float]:
    access_nodes: dict[int, float] = {}
    for point in destinations:
        for index, distance in _nearby_access_nodes(tree, coordinates, point).items():
            access_nodes[index] = min(access_nodes.get(index, float("inf")), distance)
    return access_nodes


def _building_access_distance(point: Point | None, index: int, tree: cKDTree, coordinates: np.ndarray, distances: np.ndarray) -> float | None:
    if point is None or not np.isfinite(point.x) or not np.isfinite(point.y):
        return None
    if index >= 0 and np.isfinite(distances[index]):
        return float(distances[index]) + _distance_m((point.x, point.y), tuple(coordinates[index]))
    candidates = (
        float(distances[candidate]) + access
        for candidate, access in _nearby_access_nodes(tree, coordinates, point).items()
        if np.isfinite(distances[candidate])
    )
    return min(candidates, default=None)


def _nearby_access_nodes(tree: cKDTree, coordinates: np.ndarray, point: Point) -> dict[int, float]:
    radius_degrees = DESTINATION_ACCESS_RADIUS_M / (111_320 * cos(radians(point.y)))
    indices = tree.query_ball_point((point.x, point.y), radius_degrees)
    fallback = not indices
    if not indices:
        _, nearest = tree.query((point.x, point.y))
        indices = [nearest]
    values = {}
    for index in indices:
        distance = _distance_m((point.x, point.y), tuple(coordinates[index]))
        if fallback or distance <= DESTINATION_ACCESS_RADIUS_M:
            values[index] = distance
    return values


def bike_minutes(distance_m: float, speed_kmh: float) -> float:
    return distance_m / (speed_kmh * 1_000 / 60)


def nearest_graph_nodes(graph: nx.DiGraph, points: list[tuple[float, float]]) -> list[int]:
    nodes = list(graph.nodes)
    tree = cKDTree([graph.nodes[node]["coordinate"] for node in nodes])
    _, indices = tree.query(points)
    return [nodes[index] for index in indices]


def destination_distances(graph: nx.DiGraph, destination_nodes: list[int]) -> dict[int, float]:
    return nx.multi_source_dijkstra_path_length(graph.reverse(copy=False), destination_nodes, weight="length_m")


def assign_route_distances(
    buildings: gpd.GeoDataFrame, graph: nx.DiGraph, destination_nodes: list[int]
) -> dict[str, BuildingValue]:
    points = buildings.to_crs(4326).geometry.representative_point()
    nodes = nearest_graph_nodes(graph, [(point.x, point.y) for point in points])
    distances = destination_distances(graph, destination_nodes)
    return {
        building_id: BuildingValue(
            ValueState.KNOWN if node in distances else ValueState.UNKNOWN,
            ValueKind.SCALAR,
            distances.get(node),
            coverage=1 if node in distances else 0,
            method=ValueMethod.DERIVED,
            confidence=Confidence.MEDIUM,
        )
        for building_id, node in zip(buildings["building_id"], nodes, strict=True)
    }


def _distance_m(start: tuple[float, float], end: tuple[float, float]) -> float:
    lon1, lat1 = map(radians, start)
    lon2, lat2 = map(radians, end)
    return 6_371_000 * 2 * asin(sqrt(sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2))
