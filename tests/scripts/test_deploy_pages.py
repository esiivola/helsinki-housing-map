from pathlib import Path


def test_pages_build_uses_project_subpath() -> None:
    workflow = Path(".github/workflows/deploy-pages.yml").read_text()

    assert "VITE_BASE_PATH: /helsinki-housing-map/" in workflow
