from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

from pipeline.models import RawArtifact


def cached_snapshot_path(source_id: str, source_url: str, cache_dir: Path) -> Path:
    url_key = sha256(source_url.encode()).hexdigest()
    return cache_dir / source_id / url_key


def download_snapshot(source_id: str, source_url: str, cache_dir: Path) -> RawArtifact:
    target = cached_snapshot_path(source_id, source_url, cache_dir)
    if target.is_file():
        return RawArtifact(source_id, source_url, target, _checksum(target))

    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(source_url) as response:
        with NamedTemporaryFile(dir=target.parent, suffix=".partial", delete=False) as partial:
            while chunk := response.read(1024 * 1024):
                partial.write(chunk)
            partial_path = Path(partial.name)
    partial_path.replace(target)
    return RawArtifact(source_id, source_url, target, _checksum(target))


def _checksum(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as snapshot:
        while chunk := snapshot.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
