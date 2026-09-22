from pathlib import Path

import pytest

from pipeline.models import Confidence
from pipeline.sources.helsinki_building_ownership import read_building_ownership


def test_reader_maps_the_two_supported_owner_classes(tmp_path: Path) -> None:
    snapshot = tmp_path / "building_ownership.csv"
    snapshot.write_text("building_id,luokka\nA,kaupunki\nB,muu omistaja\n")

    values = read_building_ownership(snapshot)

    assert values["A"].value == "city"
    assert values["A"].confidence is Confidence.HIGH
    assert values["B"].value == "non_city"
    assert values["B"].confidence is Confidence.LOW


def test_reader_deduplicates_repeated_identical_classifications(tmp_path: Path) -> None:
    snapshot = tmp_path / "building_ownership.csv"
    snapshot.write_text("building_id,luokka\nA,kaupunki\nA,kaupunki\n")

    values = read_building_ownership(snapshot)

    assert values["A"].value == "city"


@pytest.mark.parametrize("contents, message", [
    ("building_id,luokka\nA,other\n", "unsupported class"),
    ("building_id,luokka\nA,kaupunki\nA,muu omistaja\n", "conflicting class"),
    ("id,luokka\nA,kaupunki\n", "requires building_id,luokka header"),
])
def test_reader_rejects_ambiguous_or_invalid_input(tmp_path: Path, contents: str, message: str) -> None:
    snapshot = tmp_path / "building_ownership.csv"
    snapshot.write_text(contents)

    with pytest.raises(ValueError, match=message):
        read_building_ownership(snapshot)
