import json
import gzip
from pathlib import Path

from pipeline.verify_release import verify_release


def test_verify_release_accepts_a_complete_spatial_bundle(tmp_path: Path) -> None:
    (tmp_path / "overview" / "1000m" / "tiles" / "10").mkdir(parents=True)
    (tmp_path / "overview" / "1000m" / "layers" / "building_year" / "10").mkdir(parents=True)
    (tmp_path / "overview" / "1000m" / "tiles" / "10" / "1").mkdir()
    (tmp_path / "overview" / "1000m" / "layers" / "building_year" / "10" / "1").mkdir()
    (tmp_path / "tiles" / "geometry" / "16" / "1").mkdir(parents=True)
    (tmp_path / "tiles" / "core" / "16" / "1").mkdir(parents=True)
    (tmp_path / "tiles" / "layers" / "building_year" / "16" / "1").mkdir(parents=True)
    for path in ("sources.json", "evidence.json", "layers.json", "layer-distributions.json", "audit.json", "overview/1000m/tiles/10/1/2.geojson.gz", "overview/1000m/layers/building_year/10/1/2.json.gz", "tiles/geometry/16/1/2.geojson.gz", "tiles/core/16/1/2.json.gz", "tiles/layers/building_year/16/1/2.json.gz"):
        (tmp_path / path).write_text("{}")
    (tmp_path / "sources.json").write_text("[]")
    (tmp_path / "layers.json").write_text(json.dumps([{"layer_id": "building_year", "kind": "categorical"}]))
    (tmp_path / "layer-distributions.json").write_text(json.dumps({"version": 1, "distributions": []}))
    (tmp_path / "manifest.json").write_text(json.dumps({
        "source_manifest": "sources.json", "evidence": "evidence.json", "layer_catalogue": "layers.json", "layer_distributions": "layer-distributions.json", "audit_report": "audit.json",
        "spatial_partitions": {"overview_tiers": [{"min_zoom": 10, "max_zoom": 10, "cell_size_m": 1000, "tile_zoom": 10, "geometry_path_template": "overview/1000m/tiles/10/{x}/{y}.geojson.gz", "layer_path_template": "overview/1000m/layers/{layer_id}/10/{x}/{y}.json.gz", "tile_keys": ["1/2"]}], "building_tier": {"tile_keys": ["1/2"], "geometry_path_template": "tiles/geometry/16/{x}/{y}.geojson.gz", "core_attribute_path_template": "tiles/core/16/{x}/{y}.json.gz", "layer_attribute_path_template": "tiles/layers/{layer_id}/16/{x}/{y}.json.gz", "layer_tile_keys": {"building_year": ["1/2"]}}},
    }))

    assert verify_release(tmp_path)["building_tile_count"] == 1

    (tmp_path / "overview" / "1000m" / "layers" / "building_year" / "10" / "1" / "2.json.gz").unlink()
    try:
        verify_release(tmp_path)
    except ValueError as error:
        assert "overview layer tile" in str(error)
    else:
        raise AssertionError("expected missing overview layer tile to fail")
    (tmp_path / "overview" / "1000m" / "layers" / "building_year" / "10" / "1" / "2.json.gz").write_text("{}")

    (tmp_path / "tiles" / "layers" / "building_year" / "16" / "1" / "2.json.gz").unlink()
    try:
        verify_release(tmp_path)
    except ValueError as error:
        assert "building_year/1/2" in str(error)
    else:
        raise AssertionError("expected missing layer tile to fail")

    (tmp_path / "tiles" / "layers" / "building_year" / "16" / "1" / "2.json.gz").write_text("{}")
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    del manifest["spatial_partitions"]["building_tier"]["layer_tile_keys"]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    try:
        verify_release(tmp_path)
    except ValueError as error:
        assert "availability" in str(error)
    else:
        raise AssertionError("expected missing layer tile availability to fail")


def test_verify_release_reconciles_attribute_audit_and_evidence_references(tmp_path: Path) -> None:
    (tmp_path / "attributes").mkdir()
    (tmp_path / "sources.json").write_text(json.dumps([{"source_id": "source"}]))
    (tmp_path / "evidence.json").write_text(json.dumps([{"evidence_id": "evidence", "source_id": "source"}]))
    (tmp_path / "layers.json").write_text(json.dumps([{"layer_id": "building_year"}]))
    (tmp_path / "layer-distributions.json").write_text(json.dumps({"version": 1, "distributions": []}))
    (tmp_path / "attributes" / "Helsinki.json.gz").write_bytes(gzip.compress(json.dumps({
        "buildings": [{"building_id": "a", "municipality": "Helsinki"}],
        "building_values": [{"building_id": "a", "layer_id": "building_year", "state": "known", "evidence_ids": ["evidence"]}],
    }).encode(), mtime=0))
    (tmp_path / "audit.json").write_text(json.dumps({
        "building_count_by_municipality": {"Helsinki": 1},
        "evidence_count": 1,
        "layer_value_state_counts": {"known": 1},
        "layer_value_state_counts_by_municipality": {"Helsinki": {"known": 1}},
        "layer_value_state_counts_by_layer": {"building_year": {"known": 1}},
        "layer_value_state_counts_by_municipality_and_layer": {"Helsinki": {"building_year": {"known": 1}}},
    }))
    (tmp_path / "manifest.json").write_text(json.dumps({
        "source_manifest": "sources.json", "evidence": "evidence.json", "layer_catalogue": "layers.json",
        "attribute_partitions": ["attributes/Helsinki.json.gz"], "layer_distributions": "layer-distributions.json", "audit_report": "audit.json",
    }))

    assert verify_release(tmp_path)["building_tile_count"] == 0


def test_verify_release_rejects_attribute_values_with_unknown_evidence(tmp_path: Path) -> None:
    (tmp_path / "attributes").mkdir()
    for path, value in {
        "sources.json": [{"source_id": "source"}],
        "evidence.json": [],
        "layers.json": [{"layer_id": "building_year"}],
        "layer-distributions.json": {"version": 1, "distributions": []},
        "audit.json": {"building_count_by_municipality": {"Helsinki": 1}, "evidence_count": 0, "layer_value_state_counts": {"known": 1}, "layer_value_state_counts_by_municipality": {"Helsinki": {"known": 1}}, "layer_value_state_counts_by_layer": {"building_year": {"known": 1}}, "layer_value_state_counts_by_municipality_and_layer": {"Helsinki": {"building_year": {"known": 1}}}},
    }.items():
        (tmp_path / path).write_text(json.dumps(value))
    (tmp_path / "attributes" / "Helsinki.json.gz").write_bytes(gzip.compress(json.dumps({"buildings": [{"building_id": "a", "municipality": "Helsinki"}], "building_values": [{"building_id": "a", "layer_id": "building_year", "state": "known", "evidence_ids": ["missing"]}]}).encode(), mtime=0))
    (tmp_path / "manifest.json").write_text(json.dumps({"source_manifest": "sources.json", "evidence": "evidence.json", "layer_catalogue": "layers.json", "attribute_partitions": ["attributes/Helsinki.json.gz"], "layer_distributions": "layer-distributions.json", "audit_report": "audit.json"}))

    try:
        verify_release(tmp_path)
    except ValueError as error:
        assert "unknown evidence" in str(error)
    else:
        raise AssertionError("expected invalid evidence reference to fail")


def test_verify_release_rejects_malformed_distribution(tmp_path: Path) -> None:
    (tmp_path / "sources.json").write_text("[]")
    (tmp_path / "evidence.json").write_text("[]")
    (tmp_path / "layers.json").write_text(json.dumps([{"layer_id": "income", "kind": "numeric", "visualization_breaks": [1, 2]}]))
    (tmp_path / "layer-distributions.json").write_text(json.dumps({"version": 1, "distributions": [{"layer_id": "income", "counts": [1], "known_count": 1}]}))
    (tmp_path / "audit.json").write_text("{}")
    (tmp_path / "manifest.json").write_text(json.dumps({"source_manifest": "sources.json", "evidence": "evidence.json", "layer_catalogue": "layers.json", "layer_distributions": "layer-distributions.json", "audit_report": "audit.json", "attribute_partitions": []}))

    try:
        verify_release(tmp_path)
    except ValueError as error:
        assert "distribution" in str(error)
    else:
        raise AssertionError("expected malformed distribution to fail")


def test_verify_release_rejects_a_layer_with_an_unlisted_source(tmp_path: Path) -> None:
    (tmp_path / "sources.json").write_text(json.dumps([{"source_id": "listed"}]))
    (tmp_path / "evidence.json").write_text("[]")
    (tmp_path / "layers.json").write_text(json.dumps([{"layer_id": "building_year", "kind": "categorical", "source_ids": ["missing"]}]))
    (tmp_path / "layer-distributions.json").write_text(json.dumps({"version": 1, "distributions": []}))
    (tmp_path / "audit.json").write_text("{}")
    (tmp_path / "manifest.json").write_text(json.dumps({"source_manifest": "sources.json", "evidence": "evidence.json", "layer_catalogue": "layers.json", "layer_distributions": "layer-distributions.json", "audit_report": "audit.json"}))

    try:
        verify_release(tmp_path)
    except ValueError as error:
        assert "unknown source" in str(error)
    else:
        raise AssertionError("expected an unlisted layer source to fail")
