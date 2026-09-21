from pipeline.export.spatial_tiles import overview_cell, tile_keys_for_bbox


def test_tile_keys_cover_each_web_mercator_tile_touched_by_a_building_bbox() -> None:
    assert tile_keys_for_bbox((24.94, 60.17, 24.941, 60.171), 16) == [(37308, 18969)]
    assert tile_keys_for_bbox((0, -1, 0.01, 1), 1) == [(1, 0), (1, 1)]


def test_overview_cell_is_deterministic_in_web_mercator_metres() -> None:
    assert overview_cell(24.94, 60.17, 1000) == (2776, 8437)
