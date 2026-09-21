from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from pipeline.common.geometry import categorical_aggregate
from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState

def read_lease_areas(path: Path) -> gpd.GeoDataFrame:
    areas = gpd.read_file(path)
    if areas.crs is None:
        raise ValueError("Vantaa property map has no CRS")
    if "tyyppi" not in areas:
        raise ValueError("Vantaa property map is missing tyyppi")
    return areas.loc[areas["tyyppi"] == "vuokraalue", ["tyyppi", "geometry"]].copy()


def assign_lease_evidence(
    buildings: gpd.GeoDataFrame, lease_areas: gpd.GeoDataFrame
) -> dict[str, BuildingValue]:
    values = {
        building.building_id: BuildingValue(
            state=ValueState.UNKNOWN, kind=ValueKind.DISTRIBUTION, value=None,
            method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM,
        )
        for building in buildings[["building_id", "geometry"]].itertuples(index=False)
    }
    matches = gpd.sjoin(buildings[["building_id", "geometry"]], lease_areas[["geometry"]], how="inner", predicate="intersects")
    geometry_by_building = buildings.set_index("building_id").geometry
    for building_id, matched in matches.groupby("building_id"):
        building = geometry_by_building[building_id]
        areas = lease_areas.geometry.loc[matched["index_right"]]
        value = categorical_aggregate(
            building,
            ((area, "leased") for area in areas),
        )
        values[building_id] = BuildingValue(
            state=value.state, kind=value.kind, value=value.value,
            distribution=value.distribution, coverage=value.coverage,
            method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM,
        )
    return values
