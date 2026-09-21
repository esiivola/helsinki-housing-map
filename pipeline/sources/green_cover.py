from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pyogrio
from pyproj import Transformer
from shapely.geometry import box

from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState


def green_cover_300m(
    buildings: gpd.GeoDataFrame,
    snapshots: list[Path],
    checkpoint_dir: Path | None = None,
) -> dict[str, BuildingValue]:
    projected = buildings.to_crs(3067)[["building_id", "geometry"]].copy()
    projected["buffer"] = projected.geometry.representative_point().buffer(300)
    projected["tile"] = projected.geometry.representative_point().apply(lambda point: (int(point.x // 2_000), int(point.y // 2_000)))
    values: dict[str, BuildingValue] = {}
    indexed = [_indexed_snapshot(path) for path in snapshots]
    coverage = _coverage_geometry(snapshots)
    source_crs = {path: gpd.read_file(path, rows=1).crs for path in indexed}
    snapshot_fingerprint = _snapshot_fingerprint(snapshots)
    for tile_key, tile in projected.groupby("tile"):
        checkpoint = checkpoint_dir / f"{tile_key[0]}-{tile_key[1]}.json" if checkpoint_dir is not None else None
        cached = _read_checkpoint(checkpoint, tile, snapshot_fingerprint) if checkpoint is not None else None
        if cached is not None:
            values.update(cached)
            continue
        bounds = _bounds(tile["buffer"])
        vegetation = gpd.GeoSeries([geometry for path in indexed for geometry in _read_window(path, bounds, source_crs[path]) if geometry is not None and not geometry.is_empty], crs=3067)
        index = vegetation.sindex if len(vegetation) else None
        for row in tile.itertuples(index=False):
            if coverage is None or not coverage.covers(row.buffer):
                values[row.building_id] = BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM)
                continue
            candidates = vegetation.iloc[index.query(row.buffer, predicate="intersects")] if index else vegetation
            if len(candidates) and not candidates.is_valid.all():
                candidates = candidates.make_valid()
            green = candidates.union_all() if len(candidates) else None
            area = row.buffer.intersection(green).area if green else 0
            values[row.building_id] = BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, round(area / row.buffer.area * 100, 1), coverage=1, method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM)
        if checkpoint is not None:
            _write_checkpoint(checkpoint, tile, snapshot_fingerprint, values)
    return values


def main_cycle_route_access_m(buildings: gpd.GeoDataFrame, snapshot: Path) -> dict[str, BuildingValue]:
    routes = gpd.read_file(snapshot).to_crs(3067).geometry.union_all()
    return {
        row.building_id: BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, round(row.geometry.representative_point().distance(routes), 1), coverage=1, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
        if str(row.kunta) == "091" else BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
        for row in buildings.to_crs(3067)[["building_id", "kunta", "geometry"]].itertuples(index=False)
    }


def _bounds(geometries: gpd.GeoSeries) -> tuple[float, float, float, float]:
    west, south, east, north = geometries.total_bounds
    return float(west), float(south), float(east), float(north)


def _read_window(path: Path, bounds: tuple[float, float, float, float], source_crs: object) -> gpd.GeoSeries:
    if source_crs is None:
        raise ValueError(f"Green-cover snapshot has no CRS: {path}")
    if str(source_crs).upper() == "EPSG:3067":
        source_bounds = bounds
    else:
        transformer = Transformer.from_crs(3067, source_crs, always_xy=True)
        west, south, east, north = bounds
        corners = [transformer.transform(x, y) for x in (west, east) for y in (south, north)]
        source_bounds = min(x for x, _ in corners), min(y for _, y in corners), max(x for x, _ in corners), max(y for _, y in corners)
    return gpd.read_file(path, bbox=source_bounds, columns=[]).to_crs(3067).geometry


def _indexed_snapshot(path: Path) -> Path:
    indexed = path.with_suffix(".gpkg")
    if indexed.is_file() and indexed.stat().st_mtime >= path.stat().st_mtime:
        return indexed
    temporary = indexed.with_name(f"{indexed.stem}.partial.gpkg")
    with pyogrio.open_arrow(path, columns=[], use_pyarrow=True) as (metadata, reader):
        pyogrio.write_arrow(reader, temporary, driver="GPKG", geometry_name=metadata["geometry_name"], geometry_type=metadata["geometry_type"], crs=metadata["crs"], layer_options={"SPATIAL_INDEX": "YES"})
    temporary.replace(indexed)
    return indexed


def _snapshot_fingerprint(snapshots: list[Path]) -> list[dict[str, int | str]]:
    return [
        {"path": str(path.resolve()), "size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
        for path in snapshots
    ]


def _coverage_geometry(snapshots: list[Path]):
    bounds = []
    for snapshot in snapshots:
        try:
            completion = json.loads(Path(f"{snapshot}.complete.json").read_text())
            bbox = completion["bbox"]
            if completion.get("version") != 2 or not isinstance(bbox, list) or len(bbox) != 4:
                return None
            bounds.append(tuple(float(value) for value in bbox))
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
    if not bounds or len(set(bounds)) != 1:
        return None
    return gpd.GeoSeries([box(*bounds[0])], crs=4326).to_crs(3067).iloc[0]


def _tile_fingerprint(tile: gpd.GeoDataFrame) -> str:
    digest = hashlib.sha256()
    for row in tile.sort_values("building_id").itertuples(index=False):
        digest.update(row.building_id.encode())
        digest.update(row.geometry.wkb)
    return digest.hexdigest()


def _read_checkpoint(
    path: Path,
    tile: gpd.GeoDataFrame,
    snapshot_fingerprint: list[dict[str, int | str]],
) -> dict[str, BuildingValue] | None:
    try:
        checkpoint = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    building_ids = sorted(tile["building_id"])
    if checkpoint.get("version") != 2 or checkpoint.get("snapshots") != snapshot_fingerprint or checkpoint.get("tile") != _tile_fingerprint(tile) or sorted(checkpoint.get("values", {})) != building_ids:
        return None
    return {
        building_id: BuildingValue(ValueState(item["state"]), ValueKind.SCALAR, item["value"], coverage=item["coverage"], method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM)
        for building_id, item in checkpoint["values"].items()
    }


def _write_checkpoint(
    path: Path,
    tile: gpd.GeoDataFrame,
    snapshot_fingerprint: list[dict[str, int | str]],
    values: dict[str, BuildingValue],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    building_ids = sorted(tile["building_id"])
    checkpoint = {
        "version": 2,
        "snapshots": snapshot_fingerprint,
        "tile": _tile_fingerprint(tile),
        "values": {building_id: {"state": values[building_id].state.value, "value": values[building_id].value, "coverage": values[building_id].coverage} for building_id in building_ids},
    }
    temporary = path.with_suffix(".partial.json")
    temporary.write_text(json.dumps(checkpoint, separators=(",", ":")))
    temporary.replace(path)
