from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely import area, intersection

from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState


def read_noise_zones(path: Path) -> gpd.GeoDataFrame:
    zones = gpd.read_file(path)
    if zones.crs is None:
        raise ValueError("noise zones source has no CRS")
    if "db_hi" not in zones:
        raise ValueError("noise zones source is missing db_hi")
    values = zones["db_hi"]
    numeric = values.notna() & values.map(lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0)
    if (values.notna() & ~numeric).any():
        raise ValueError("noise zones source has invalid db_hi")
    return zones.loc[numeric, ["db_hi", "geometry"]].copy()


def assign_noise_upper_by_intersection(
    buildings: gpd.GeoDataFrame, zones: gpd.GeoDataFrame
) -> dict[str, BuildingValue]:
    values = {
        building.building_id: BuildingValue(
            ValueState.UNKNOWN, ValueKind.SCALAR, None,
            method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM,
        )
        for building in buildings[["building_id", "geometry"]].itertuples(index=False)
    }
    valid_buildings = buildings.loc[~(buildings.geometry.is_empty | (buildings.geometry.area == 0))].reset_index(names="building_row")
    matches = gpd.sjoin(valid_buildings[["building_row", "building_id", "geometry"]], zones[["db_hi", "geometry"]], how="inner", predicate="intersects")
    geometry_by_row = valid_buildings.set_index("building_row").geometry
    matches["intersection_area"] = area(intersection(matches.geometry.array, zones.geometry.loc[matches["index_right"]].array))
    for building_row, matches_for_building in matches.groupby("building_row"):
        coverage = matches_for_building["intersection_area"].sum() / geometry_by_row.at[building_row].area
        building_id = matches_for_building["building_id"].iloc[0]
        values[building_id] = BuildingValue(
            ValueState.KNOWN if coverage == 1 else ValueState.PARTIAL,
            ValueKind.SCALAR,
            max(matches_for_building["db_hi"]),
            coverage=coverage,
            method=ValueMethod.AGGREGATED,
            confidence=Confidence.MEDIUM,
        )
    return values
