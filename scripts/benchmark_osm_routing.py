from pathlib import Path

from scipy.spatial import cKDTree

from pipeline.sources.osm import (
    extract_destinations,
    extract_pedestrian_sparse_graph,
    sparse_destination_distances,
)


snapshot = Path("data/raw/hsl_osm_2026-08-25.pbf")
nodes, coordinates, graph = extract_pedestrian_sparse_graph(snapshot)
supermarkets = extract_destinations(snapshot)["supermarket"]
_, indices = cKDTree(coordinates).query([(point.x, point.y) for point in supermarkets.geometry])
distances = sparse_destination_distances(graph, nodes, [nodes[index] for index in indices])
print({"nodes": len(nodes), "edges": graph.nnz, "reachable": int((distances < float("inf")).sum())})
