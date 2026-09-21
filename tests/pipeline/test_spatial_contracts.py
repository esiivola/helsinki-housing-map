from __future__ import annotations

from shapely.geometry import Polygon

from pipeline.common.geometry import categorical_aggregate, numeric_aggregate
from pipeline.models import ValueKind, ValueState


def square(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def test_numeric_aggregation_is_area_weighted_with_full_coverage() -> None:
    building = square(0, 0, 10, 10)
    result = numeric_aggregate(
        building,
        [(square(0, 0, 6, 10), 10), (square(6, 0, 10, 10), 20)],
    )

    assert result.state is ValueState.KNOWN
    assert result.kind is ValueKind.SCALAR
    assert result.value == 14
    assert result.coverage == 1


def test_categorical_aggregation_retains_small_overlaps_and_mixed_shares() -> None:
    building = square(0, 0, 10, 10)
    result = categorical_aggregate(
        building,
        [(square(0, 0, 6, 10), "city"), (square(6, 0, 10, 10), "non_city")],
    )

    assert result.state is ValueState.KNOWN
    assert result.kind is ValueKind.DISTRIBUTION
    assert result.value == "mixed"
    assert result.distribution == {"city": 0.6, "non_city": 0.4}
    assert result.coverage == 1


def test_partial_coverage_remains_partial_instead_of_becoming_unknown_or_zero() -> None:
    building = square(0, 0, 10, 10)
    result = numeric_aggregate(building, [(square(0, 0, 7, 10), 10)])

    assert result.state is ValueState.PARTIAL
    assert result.value == 10
    assert result.coverage == 0.7


def test_one_percent_valid_overlap_is_retained() -> None:
    building = square(0, 0, 10, 10)
    result = categorical_aggregate(building, [(square(0, 0, 0.1, 10), "city")])

    assert result.state is ValueState.PARTIAL
    assert result.value == "city"
    assert result.coverage == 0.01


def test_categorical_aggregation_does_not_double_count_overlapping_sources() -> None:
    building = square(0, 0, 10, 10)
    result = categorical_aggregate(
        building,
        [(square(0, 0, 10, 10), "city"), (square(0, 0, 10, 10), "city")],
    )

    assert result.state is ValueState.KNOWN
    assert result.coverage == 1
    assert result.distribution == {"city": 1}


def test_no_covered_area_is_explicitly_unknown() -> None:
    building = square(0, 0, 10, 10)
    result = numeric_aggregate(building, [(square(20, 20, 30, 30), 10)])

    assert result.state is ValueState.UNKNOWN
    assert result.value is None
    assert result.coverage == 0
