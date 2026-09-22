from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from pipeline.common.geometry import categorical_aggregate
from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState


def read_city_land_areas(path: Path) -> gpd.GeoDataFrame:
    areas = gpd.read_file(path)
    if areas.crs is None:
        raise ValueError("Espoo city-land snapshot has no CRS")
    return areas[["geometry"]].loc[~areas.geometry.is_empty].copy()


def assign_city_owner_evidence(
    buildings: gpd.GeoDataFrame, city_land_areas: gpd.GeoDataFrame
) -> dict[str, BuildingValue]:
    city_land = city_land_areas.geometry.union_all()
    values: dict[str, BuildingValue] = {}
    for building in buildings[["building_id", "geometry"]].itertuples(index=False):
        covered = building.geometry.intersection(city_land).area / building.geometry.area
        fully_city_owned = covered >= 1 - 1e-9
        outside_city_land = covered <= 1e-9
        values[building.building_id] = BuildingValue(
            state=ValueState.KNOWN if fully_city_owned or outside_city_land else ValueState.UNKNOWN,
            kind=ValueKind.SCALAR,
            value="city" if fully_city_owned else "non_city" if outside_city_land else None,
            coverage=covered,
            method=ValueMethod.AGGREGATED,
            confidence=Confidence.HIGH if fully_city_owned else Confidence.LOW,
        )
    return values


def assign_city_owner_coverage(
    buildings: gpd.GeoDataFrame, city_land_areas: gpd.GeoDataFrame
) -> dict[str, BuildingValue]:
    values = {
        building.building_id: BuildingValue(
            ValueState.UNKNOWN, ValueKind.DISTRIBUTION, None,
            method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM,
        )
        for building in buildings[["building_id", "geometry"]].itertuples(index=False)
    }
    matches = gpd.sjoin(
        buildings[["building_id", "geometry"]], city_land_areas[["geometry"]],
        how="inner", predicate="intersects",
    )
    geometry_by_building = buildings.set_index("building_id").geometry
    for building_id, matched in matches.groupby("building_id"):
        value = categorical_aggregate(
            geometry_by_building[building_id],
            ((area, "city_owned") for area in city_land_areas.geometry.loc[matched["index_right"]]),
        )
        values[building_id] = BuildingValue(
            value.state, value.kind, value.value, distribution=value.distribution,
            coverage=value.coverage, method=ValueMethod.AGGREGATED,
            confidence=Confidence.MEDIUM,
        )
    return values
