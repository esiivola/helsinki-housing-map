from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: record_performance.py AUDIT_JSON PERFORMANCE_JSON")
    audit_path, report_path = map(Path, sys.argv[1:])
    audit = json.loads(audit_path.read_text())
    report = json.loads(report_path.read_text())
    if not isinstance(audit, dict) or not isinstance(report, dict):
        raise ValueError("audit and performance report must be JSON objects")
    reference_machine = report.get("reference_machine")
    browser = report.get("browser")
    preference_update = report.get("preference_update_p95_ms")
    inspector = report.get("loaded_inspector_p95_ms")
    if not isinstance(reference_machine, str) or not reference_machine or not isinstance(browser, str) or not browser:
        raise ValueError("performance report is missing reference details")
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in (preference_update, inspector)):
        raise ValueError("performance report contains invalid timings")
    if preference_update > 200:
        raise ValueError("preference update p95 exceeds 200 ms")
    if inspector > 100:
        raise ValueError("loaded inspector p95 exceeds 100 ms")
    audit["reference_performance"] = {
        "browser": browser,
        "loaded_inspector_p95_ms": inspector,
        "preference_update_p95_ms": preference_update,
        "reference_machine": reference_machine,
    }
    audit_path.write_text(json.dumps(audit, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
