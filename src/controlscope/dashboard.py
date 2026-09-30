"""Generate a self-contained, source-linked local review workspace."""

from __future__ import annotations

import json
from pathlib import Path

from .pipeline import REGISTRY
from .store import connect, finding_detail

TEMPLATE = Path(__file__).with_name("dashboard_template.html")


def write_dashboard(db_path: Path, out_path: Path) -> dict:
    conn = connect(db_path)
    try:
        findings = [finding_detail(conn, row[0]) for row in conn.execute(
            "SELECT finding_id FROM findings ORDER BY finding_id")]
        runs = [json.loads(row[0]) for row in conn.execute(
            "SELECT manifest_json FROM runs ORDER BY created_at, run_id")]
    finally:
        conn.close()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["controls"]
    payload = json.dumps({"findings": findings, "registry": registry, "runs": runs},
                         separators=(",", ":"))
    # The payload is embedded in HTML, so closing script tags must remain inert.
    payload = payload.replace("<", "\\u003c")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload),
                        encoding="utf-8")
    return {"dashboard": str(out_path), "findings": len(findings)}
