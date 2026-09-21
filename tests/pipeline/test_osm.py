from pathlib import Path

import geopandas as gpd
from scipy.sparse import csr_matrix
from shapely.geometry import Point

from pipeline.models import ValueState
from pipeline.sources.osm import PRISMA_TRIPLA, assign_route_distances, assign_sparse_route_distances, bike_minutes, destination_distances, extract_basemap, extract_cycling_sparse_graph, extract_destinations, extract_pedestrian_edges, extract_pedestrian_graph, extract_pedestrian_sparse_graph, nearest_graph_nodes, sparse_destination_distances


def test_osm_destinations_follow_the_configured_shop_and_forest_rules() -> None:
    destinations = extract_destinations(Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm")

    assert len(destinations["grocery"]) == 2
    assert len(destinations["supermarket"]) == 1
    assert len(destinations["forest"]) == 1
    assert len(destinations["shore"]) == 2


def test_osm_destinations_group_store_brands_and_other_shops(tmp_path: Path) -> None:
    path = tmp_path / "stores.osm"
    path.write_text('''<osm version="0.6"><node id="1" lat="60.1" lon="24.9"><tag k="shop" v="supermarket"/><tag k="brand" v="Lidl"/></node><node id="2" lat="60.1" lon="24.91"><tag k="shop" v="convenience"/><tag k="name" v="Alepa Katajanokka"/></node><node id="3" lat="60.1" lon="24.92"><tag k="shop" v="supermarket"/><tag k="name" v="Independent Market"/></node></osm>''')

    destinations = extract_destinations(path)

    assert len(destinations["grocery_store_lidl"]) == 1
    assert len(destinations["grocery_store_alepa"]) == 1
    assert len(destinations["grocery_store_other_supermarket"]) == 1
    assert destinations["grocery_store_lidl"].iloc[0]["name"] == "Lidl"


def test_osm_destinations_include_prisma_tripla_when_the_snapshot_omits_it(tmp_path: Path) -> None:
    path = tmp_path / "stores.osm"
    path.write_text('<osm version="0.6"></osm>')

    destinations = extract_destinations(path)

    assert list(destinations["grocery_store_prisma"].geometry) == [PRISMA_TRIPLA]


def test_osm_destinations_do_not_duplicate_prisma_tripla_from_a_refreshed_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "stores.osm"
    path.write_text('<osm version="0.6"><node id="6888009532" lat="60.19846" lon="24.92991"><tag k="shop" v="supermarket"/><tag k="brand" v="Prisma"/></node></osm>')

    destinations = extract_destinations(path)

    assert list(destinations["grocery_store_prisma"].geometry) == [PRISMA_TRIPLA]


def test_osm_destinations_include_service_nodes_and_areas(tmp_path: Path) -> None:
    path = tmp_path / "services.osm"
    path.write_text('''<osm version="0.6"><node id="1" lat="60.1" lon="24.9"><tag k="amenity" v="kindergarten"/></node><node id="2" lat="60.1" lon="24.91"><tag k="amenity" v="school"/></node><node id="3" lat="60.1" lon="24.92"><tag k="amenity" v="doctors"/></node><node id="4" lat="60.11" lon="24.9"/><node id="5" lat="60.11" lon="24.91"/><node id="6" lat="60.11" lon="24.92"/><way id="10"><nd ref="4"/><nd ref="5"/><nd ref="6"/><nd ref="4"/><tag k="amenity" v="library"/><tag k="area" v="yes"/></way></osm>''')

    destinations = extract_destinations(path)

    assert len(destinations["daycare"]) == 1
    assert len(destinations["school"]) == 1
    assert len(destinations["healthcare"]) == 1
    assert len(destinations["library"]) == 1


def test_osm_destinations_extract_explicit_private_healthcare_brands(tmp_path: Path) -> None:
    path = tmp_path / "healthcare.osm"
    path.write_text('''<osm version="0.6"><node id="1" lat="60.1" lon="24.9"><tag k="healthcare" v="clinic"/><tag k="brand" v="Mehiläinen"/></node><node id="2" lat="60.1" lon="24.91"><tag k="amenity" v="doctors"/><tag k="name" v="Terveystalo Kamppi"/></node><node id="3" lat="60.1" lon="24.92"><tag k="amenity" v="clinic"/><tag k="operator" v="Pihlajalinna"/></node></osm>''')

    destinations = extract_destinations(path)

    assert len(destinations["health_provider_mehilainen"]) == 1
    assert len(destinations["health_provider_terveystalo"]) == 1
    assert len(destinations["health_provider_pihlajalinna"]) == 1


def test_osm_pedestrian_graph_extracts_routable_ways() -> None:
    edges = extract_pedestrian_edges(Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm")

    assert edges == [(1, 2), (1, 2)]


def test_osm_pedestrian_graph_has_bidirectional_weighted_edges() -> None:
    graph = extract_pedestrian_graph(Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm")

    assert graph.has_edge(1, 2)
    assert graph.has_edge(2, 1)
    assert graph[1][2]["length_m"] > 0


def test_nearest_graph_nodes_snaps_points_to_routable_nodes() -> None:
    graph = extract_pedestrian_graph(Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm")

    assert nearest_graph_nodes(graph, [(24.9001, 60.1001)]) == [1]


def test_destination_distances_runs_from_all_destination_nodes() -> None:
    graph = extract_pedestrian_graph(Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm")

    distances = destination_distances(graph, [2])

    assert distances[2] == 0
    assert distances[1] > 0


def test_route_distances_assigns_buildings_from_snapped_representative_points() -> None:
    graph = extract_pedestrian_graph(Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm")
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.9, 60.1)], crs=4326)

    value = assign_route_distances(buildings, graph, [2])["a"]

    assert value.state is ValueState.KNOWN
    assert value.value > 0


def test_sparse_graph_returns_destination_distances() -> None:
    nodes, _, graph = extract_pedestrian_sparse_graph(Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm")

    distances = sparse_destination_distances(graph, nodes, [2])

    assert distances[nodes.index(2)] == 0


def test_sparse_route_distances_assigns_building_points() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm"
    nodes, coordinates, graph = extract_pedestrian_sparse_graph(path)
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.9, 60.1)], crs=4326)

    value = assign_sparse_route_distances(buildings, nodes, coordinates, graph, [Point(24.91, 60.1)])["a"]

    assert value.state is ValueState.KNOWN


def test_sparse_route_distances_uses_nearby_connected_destination_access_node() -> None:
    nodes = [1, 2, 3]
    coordinates = [[24.9, 60.1], [24.9004, 60.1], [24.901, 60.1]]
    graph = csr_matrix([[0, 0, 0], [0, 0, 40], [0, 40, 0]])
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.901, 60.1)], crs=4326)

    value = assign_sparse_route_distances(buildings, nodes, coordinates, graph, [Point(24.9, 60.1)])["a"]

    assert value.state is ValueState.KNOWN
    assert 40 < value.value < 100


def test_sparse_route_distances_uses_connected_destination_node_beyond_fifty_metres() -> None:
    nodes = [1, 2, 3]
    coordinates = [[24.9, 60.1], [24.9015, 60.1], [24.902, 60.1]]
    graph = csr_matrix([[0, 0, 0], [0, 0, 40], [0, 40, 0]])
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.902, 60.1)], crs=4326)

    value = assign_sparse_route_distances(buildings, nodes, coordinates, graph, [Point(24.9, 60.1)])["a"]

    assert value.state is ValueState.KNOWN
    assert 100 < value.value < 250


def test_sparse_route_distances_uses_nearby_connected_building_access_node() -> None:
    nodes = [1, 2, 3]
    coordinates = [[24.9, 60.1], [24.9004, 60.1], [24.901, 60.1]]
    graph = csr_matrix([[0, 0, 0], [0, 0, 40], [0, 40, 0]])
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.9, 60.1)], crs=4326)

    value = assign_sparse_route_distances(buildings, nodes, coordinates, graph, [Point(24.901, 60.1)])["a"]

    assert value.state is ValueState.KNOWN
    assert 40 < value.value < 100


def test_sparse_route_distances_keeps_missing_destination_category_unknown() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm"
    nodes, coordinates, graph = extract_pedestrian_sparse_graph(path)
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.9, 60.1)], crs=4326)

    assert assign_sparse_route_distances(buildings, nodes, coordinates, graph, [])["a"].state is ValueState.UNKNOWN


def test_sparse_route_distances_keeps_invalid_building_origin_unknown() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm"
    nodes, coordinates, graph = extract_pedestrian_sparse_graph(path)
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(float("inf"), 60.1)], crs=4326)

    value = assign_sparse_route_distances(buildings, nodes, coordinates, graph, [Point(24.91, 60.1)])["a"]

    assert value.state is ValueState.UNKNOWN


def test_cycling_graph_excludes_footways_and_keeps_cycleways() -> None:
    nodes, _, graph = extract_cycling_sparse_graph(Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm")

    assert graph.nnz == 2
    assert nodes == [1, 2]


def test_bike_minutes_uses_the_configured_fixed_speed() -> None:
    assert bike_minutes(1_500, 15) == 6


def test_osm_basemap_keeps_only_low_detail_context_features(tmp_path: Path) -> None:
    path = tmp_path / "basemap.osm"
    path.write_text('''<osm version="0.6"><node id="1" lat="60.1" lon="24.9"/><node id="2" lat="60.1" lon="24.91"/><node id="3" lat="60.11" lon="24.91"/><node id="4" lat="60.11" lon="24.9"/><way id="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/></way><way id="2"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="natural" v="water"/></way><way id="3"><nd ref="1"/><nd ref="2"/><tag k="highway" v="footway"/></way><way id="4"><nd ref="1"/><nd ref="3"/><tag k="railway" v="rail"/></way><way id="5"><nd ref="2"/><nd ref="4"/><tag k="waterway" v="river"/></way><way id="6"><nd ref="3"/><nd ref="4"/><tag k="natural" v="coastline"/></way></osm>''')

    basemap = extract_basemap(path)

    assert [feature["properties"]["kind"] for feature in basemap["features"]] == ["road-major", "rail", "waterway", "coastline", "water"]
