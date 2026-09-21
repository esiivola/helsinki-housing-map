from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_record_performance_adds_a_validated_reference_run_to_audit(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    report = tmp_path / "performance.json"
    audit.write_text(json.dumps({"building_count_by_municipality": {"Helsinki": 1}}))
    report.write_text(json.dumps({
        "reference_machine": "Apple Silicon MacBook Pro",
        "browser": "Chromium 140.0",
        "preference_update_p95_ms": 120.5,
        "loaded_inspector_p95_ms": 80.25,
    }))

    subprocess.run([sys.executable, "scripts/record_performance.py", str(audit), str(report)], check=True)

    assert json.loads(audit.read_text())["reference_performance"] == {
        "browser": "Chromium 140.0",
        "loaded_inspector_p95_ms": 80.25,
        "preference_update_p95_ms": 120.5,
        "reference_machine": "Apple Silicon MacBook Pro",
    }


def test_record_performance_rejects_a_failed_target(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    report = tmp_path / "performance.json"
    audit.write_text("{}")
    report.write_text(json.dumps({
        "reference_machine": "test",
        "browser": "test",
        "preference_update_p95_ms": 201,
        "loaded_inspector_p95_ms": 10,
    }))

    result = subprocess.run([sys.executable, "scripts/record_performance.py", str(audit), str(report)], capture_output=True, text=True)

    assert result.returncode != 0
    assert "preference update" in result.stderr
