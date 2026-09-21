from __future__ import annotations

from collections.abc import Iterable

from shapely import union_all
from shapely.geometry.base import BaseGeometry

from pipeline.models import BuildingValue, ValueKind, ValueState


def numeric_aggregate(
    building: BaseGeometry, source_values: Iterable[tuple[BaseGeometry, float]]
) -> BuildingValue:
    weighted_value = 0.0
    covered_area = 0.0
    building_area = building.area

    for source, value in source_values:
        area = building.intersection(source).area
        weighted_value += area * value
        covered_area += area

    if covered_area == 0:
        return BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None)

    coverage = covered_area / building_area
    state = ValueState.KNOWN if coverage == 1 else ValueState.PARTIAL
    return BuildingValue(
        state=state,
        kind=ValueKind.SCALAR,
        value=weighted_value / covered_area,
        coverage=coverage,
    )


def categorical_aggregate(
    building: BaseGeometry, source_values: Iterable[tuple[BaseGeometry, str]]
) -> BuildingValue:
    building_area = building.area
    geometries: dict[str, list[BaseGeometry]] = {}

    for source, category in source_values:
        geometries.setdefault(category, []).append(source)

    areas = {
        category: building.intersection(union_all(sources)).area
        for category, sources in geometries.items()
    }

    covered_area = sum(areas.values())
    if covered_area == 0:
        return BuildingValue(ValueState.UNKNOWN, ValueKind.DISTRIBUTION, None)

    distribution = {category: area / building_area for category, area in areas.items()}
    coverage = covered_area / building_area
    value = next(iter(distribution)) if len(distribution) == 1 else "mixed"
    state = ValueState.KNOWN if coverage == 1 else ValueState.PARTIAL
    return BuildingValue(
        state=state,
        kind=ValueKind.DISTRIBUTION,
        value=value,
        coverage=coverage,
        distribution=distribution,
    )
