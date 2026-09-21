from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

import pytest

from pipeline.common.download import cached_snapshot_path, download_snapshot


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "raw_snapshot.txt"


def test_download_caches_a_checksummed_immutable_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text(FIXTURE_PATH.read_text())
    cache_dir = tmp_path / "cache"

    first = download_snapshot("fixture_source", source.as_uri(), cache_dir)
    source.unlink()
    second = download_snapshot("fixture_source", source.as_uri(), cache_dir)

    assert first == second
    assert first.path.read_text() == "synthetic immutable source snapshot\n"
    assert first.checksum.startswith("sha256:")


def test_partial_snapshot_is_never_treated_as_complete(tmp_path: Path) -> None:
    source = tmp_path / "missing-source.txt"
    cache_dir = tmp_path / "cache"
    partial = cached_snapshot_path("fixture_source", source.as_uri(), cache_dir).with_suffix(".partial")
    partial.parent.mkdir(parents=True)
    partial.write_text("incomplete")

    with pytest.raises(URLError):
        download_snapshot("fixture_source", source.as_uri(), cache_dir)
