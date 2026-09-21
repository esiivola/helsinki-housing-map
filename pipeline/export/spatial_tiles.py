from __future__ import annotations

import math


def tile_keys_for_bbox(bounds: tuple[float, float, float, float], zoom: int) -> list[tuple[int, int]]:
    west, south, east, north = bounds
    if not all(math.isfinite(value) for value in bounds) or west < -180 or east > 180 or south < -90 or north > 90:
        return []
    limit = 2**zoom - 1
    x0 = _tile_x(west, zoom)
    x1 = _tile_x(east, zoom)
    y0 = _tile_y(north, zoom)
    y1 = _tile_y(south, zoom)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if 0 <= x <= limit and 0 <= y <= limit]


def _tile_x(longitude: float, zoom: int) -> int:
    return math.floor((longitude + 180) / 360 * 2**zoom)


def _tile_y(latitude: float, zoom: int) -> int:
    clipped = max(-85.05112878, min(85.05112878, latitude))
    radians = math.radians(clipped)
    return math.floor((1 - math.asinh(math.tan(radians)) / math.pi) / 2 * 2**zoom)


def overview_cell(longitude: float, latitude: float, size_m: int) -> tuple[int, int]:
    radius = 6378137
    x = radius * math.radians(longitude)
    y = radius * math.asinh(math.tan(math.radians(latitude)))
    return math.floor(x / size_m), math.floor(y / size_m)


def overview_cell_polygon(x_index: int, y_index: int, size_m: int) -> list[list[float]]:
    return [_lonlat(x_index * size_m, y_index * size_m), _lonlat((x_index + 1) * size_m, y_index * size_m), _lonlat((x_index + 1) * size_m, (y_index + 1) * size_m), _lonlat(x_index * size_m, (y_index + 1) * size_m), _lonlat(x_index * size_m, y_index * size_m)]


def _lonlat(x: float, y: float) -> list[float]:
    radius = 6378137
    return [math.degrees(x / radius), math.degrees(math.atan(math.sinh(y / radius)))]
