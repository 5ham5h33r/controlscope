"""SQLite demo store. Source rows, findings, and review events retain lineage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, manifest_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS runs_no_update BEFORE UPDATE ON runs
BEGIN SELECT RAISE(ABORT, 'runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS runs_no_delete BEFORE DELETE ON runs
BEGIN SELECT RAISE(ABORT, 'runs are append-only'); END;
CREATE TABLE IF NOT EXISTS source_rows (
  run_id TEXT NOT NULL REFERENCES runs(run_id), table_name TEXT NOT NULL,
  row_id TEXT NOT NULL, row_json TEXT NOT NULL,
  PRIMARY KEY (run_id, table_name, row_id)
);
CREATE TRIGGER IF NOT EXISTS source_rows_no_update BEFORE UPDATE ON source_rows
BEGIN SELECT RAISE(ABORT, 'source rows are immutable'); END;
CREATE TRIGGER IF NOT EXISTS source_rows_no_delete BEFORE DELETE ON source_rows
BEGIN SELECT RAISE(ABORT, 'source rows are immutable'); END;
CREATE TABLE IF NOT EXISTS findings (
  finding_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
  control_id TEXT NOT NULL, control_version TEXT NOT NULL, entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL, business_unit TEXT NOT NULL, detail TEXT NOT NULL,
  base_risk INTEGER NOT NULL CHECK (base_risk BETWEEN 0 AND 100),
  risk_score INTEGER NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
  created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS findings_no_update BEFORE UPDATE ON findings
BEGIN SELECT RAISE(ABORT, 'findings are immutable'); END;
CREATE TRIGGER IF NOT EXISTS findings_no_delete BEFORE DELETE ON findings
BEGIN SELECT RAISE(ABORT, 'findings are immutable'); END;
CREATE TABLE IF NOT EXISTS evidence (
  finding_id TEXT NOT NULL REFERENCES findings(finding_id),
  run_id TEXT NOT NULL, table_name TEXT NOT NULL, row_id TEXT NOT NULL,
  PRIMARY KEY (finding_id, table_name, row_id),
  FOREIGN KEY (run_id, table_name, row_id) REFERENCES source_rows(run_id, table_name, row_id)
);
CREATE TRIGGER IF NOT EXISTS evidence_no_update BEFORE UPDATE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence is immutable'); END;
CREATE TABLE IF NOT EXISTS review_actions (
  action_id INTEGER PRIMARY KEY AUTOINCREMENT,
  finding_id TEXT NOT NULL REFERENCES findings(finding_id),
  action TEXT NOT NULL CHECK (action IN ('confirm','dismiss','override')),
  original_status TEXT NOT NULL, replacement_status TEXT NOT NULL,
  original_score INTEGER NOT NULL, replacement_score INTEGER NOT NULL,
  actor TEXT NOT NULL, reason TEXT NOT NULL, acted_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS review_actions_no_update BEFORE UPDATE ON review_actions
BEGIN SELECT RAISE(ABORT, 'review actions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS review_actions_no_delete BEFORE DELETE ON review_actions
BEGIN SELECT RAISE(ABORT, 'review actions are append-only'); END;
CREATE TABLE IF NOT EXISTS enrichments (
  finding_id TEXT NOT NULL REFERENCES findings(finding_id), provider TEXT NOT NULL,
  model TEXT NOT NULL, prompt_version TEXT NOT NULL, content_json TEXT NOT NULL,
  created_at TEXT NOT NULL, PRIMARY KEY (finding_id, provider, model, prompt_version)
);
CREATE VIEW IF NOT EXISTS finding_status AS
SELECT f.*, COALESCE((SELECT a.replacement_status FROM review_actions a
  WHERE a.finding_id=f.finding_id ORDER BY a.action_id DESC LIMIT 1), 'open') AS status,
  COALESCE((SELECT a.replacement_score FROM review_actions a
  WHERE a.finding_id=f.finding_id ORDER BY a.action_id DESC LIMIT 1), f.risk_score) AS current_score
FROM findings f;
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def finding_detail(conn: sqlite3.Connection, finding_id: str) -> dict:
    row = conn.execute("SELECT * FROM finding_status WHERE finding_id=?", (finding_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown finding: {finding_id}")
    result = dict(row)
    result["evidence"] = [
        {"table": item["table_name"], "row_id": item["row_id"],
         "row": json.loads(item["row_json"])}
        for item in conn.execute("""
            SELECT e.table_name, e.row_id, s.row_json FROM evidence e
            JOIN source_rows s USING (run_id, table_name, row_id)
            WHERE e.finding_id=? ORDER BY e.table_name, e.row_id
        """, (finding_id,))
    ]
    result["review_history"] = [dict(item) for item in conn.execute(
        "SELECT * FROM review_actions WHERE finding_id=? ORDER BY action_id", (finding_id,))]
    enrichment = conn.execute(
        "SELECT content_json FROM enrichments WHERE finding_id=? ORDER BY created_at DESC LIMIT 1",
        (finding_id,),
    ).fetchone()
    result["enrichment"] = json.loads(enrichment[0]) if enrichment else None
    return result


def integrity_errors(conn: sqlite3.Connection, run_id: str | None = None) -> list[str]:
    condition = "WHERE f.run_id=?" if run_id else ""
    params = (run_id,) if run_id else ()
    errors = [
        f"{row['finding_id']}: no evidence" for row in conn.execute(
            f"""SELECT f.finding_id FROM findings f LEFT JOIN evidence e
            ON e.finding_id=f.finding_id {condition}
            GROUP BY f.finding_id HAVING COUNT(e.row_id)=0""", params)
    ]
    errors.extend(str(tuple(row)) for row in conn.execute("PRAGMA foreign_key_check"))
    return errors
