from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

import geopandas as gpd

from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState


def normalize_median_income(record: Mapping[str, object], field: str = "tr_mtu") -> BuildingValue:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value == -1:
        return BuildingValue(
            state=ValueState.UNKNOWN,
            kind=ValueKind.SCALAR,
            value=None,
            method=ValueMethod.DIRECT,
            confidence=Confidence.MEDIUM,
        )
    return BuildingValue(
        state=ValueState.KNOWN,
        kind=ValueKind.SCALAR,
        value=float(value),
        coverage=1,
        method=ValueMethod.DIRECT,
        confidence=Confidence.MEDIUM,
    )


def assign_income_by_point(buildings: gpd.GeoDataFrame, areas: gpd.GeoDataFrame) -> dict[str, BuildingValue]:
    points = buildings[["building_id", "geometry"]].copy()
    points.geometry = points.representative_point()
    matches = gpd.sjoin(points, areas[["tr_mtu", "geometry"]], how="left", predicate="within")
    return {
        row.building_id: normalize_median_income({"tr_mtu": row.tr_mtu})
        for row in matches.itertuples()
    }
