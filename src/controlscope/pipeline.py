"""Reproducible run orchestration and review actions."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from .controls import evaluate, load_registry
from .data import TABLE_FIELDS, dataset_hash, read_dataset, utc_now
from .store import connect, integrity_errors

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "controls" / "registry.json"
ROW_KEYS = {"vendors": "vendor_id", "users": "user_id",
            "transactions": "transaction_id", "access_events": "event_id"}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _code_hash() -> str:
    files = sorted((ROOT / "src" / "controlscope").glob("*.py"))
    content = b"".join(path.name.encode() + b"\0" + path.read_bytes() for path in files)
    return hashlib.sha256(content).hexdigest()


def _git_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "uncommitted"


def run(data_dir: Path, db_path: Path, registry_path: Path = REGISTRY) -> dict:
    dataset = read_dataset(data_dir)
    metadata = json.loads((data_dir / "dataset.json").read_text(encoding="utf-8"))
    if metadata.get("synthetic") is not True:
        raise ValueError("Only synthetic datasets are accepted by the public demo")
    registry = load_registry(registry_path)
    configs = {row["id"]: row for row in registry["controls"]}
    candidates = evaluate(dataset)
    seen_controls = {item.control_id for item in candidates}
    if seen_controls != set(configs):
        missing = set(configs) - seen_controls
        raise ValueError(f"Demo data did not exercise controls: {sorted(missing)}")
    fingerprints = {
        "dataset_sha256": dataset_hash(dataset), "code_sha256": _code_hash(),
        "registry_sha256": _digest(registry), "seed": metadata["seed"],
        "as_of": metadata["as_of"], "risk_formula_version": "1.0.0",
    }
    run_id = _digest(fingerprints)[:20]
    manifest = {**fingerprints, "run_id": run_id, "code_commit": _git_sha(),
                "registry_version": registry["registry_version"],
                "control_versions": {key: row["version"] for key, row in configs.items()},
                "gemini_prompt_version": "1.0.0", "created_at": utc_now(),
                "source_tables": {name: len(rows) for name, rows in dataset.items()}}
    conn = connect(db_path)
    if conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
        conn.close()
        return {"run_id": run_id, "findings": len(candidates), "reused": True}
    try:
        with conn:
            conn.execute("INSERT INTO runs VALUES (?,?,?)",
                         (run_id, manifest["created_at"], json.dumps(manifest, sort_keys=True)))
            for table, rows in dataset.items():
                for row in rows:
                    conn.execute("INSERT INTO source_rows VALUES (?,?,?,?)",
                                 (run_id, table, row[ROW_KEYS[table]], json.dumps(row, sort_keys=True)))
            for item in candidates:
                spec = configs[item.control_id]
                evidence_count = len(item.evidence)
                score = min(100, int(spec["base_risk"]) + min(15, 5 * (evidence_count - 1)))
                finding_id = _digest([run_id, item.control_id, item.entity_type,
                                      item.entity_id, item.evidence])[:20]
                conn.execute("""INSERT INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                             (finding_id, run_id, item.control_id, spec["version"],
                              item.entity_type, item.entity_id, item.business_unit,
                              item.detail, spec["base_risk"], score, manifest["created_at"]))
                for table, row_id in item.evidence:
                    if table not in TABLE_FIELDS:
                        raise ValueError(f"Unknown evidence table: {table}")
                    conn.execute("INSERT INTO evidence VALUES (?,?,?,?)",
                                 (finding_id, run_id, table, row_id))
            errors = integrity_errors(conn, run_id)
            if errors:
                raise ValueError(f"Evidence integrity errors: {errors}")
    finally:
        conn.close()
    return {"run_id": run_id, "findings": len(candidates), "reused": False}


def review(db_path: Path, finding_id: str, action: str, actor: str, reason: str,
           replacement_score: int | None = None) -> dict:
    if action not in {"confirm", "dismiss", "override"}:
        raise ValueError("Action must be confirm, dismiss, or override")
    if not actor.strip() or not reason.strip():
        raise ValueError("Actor and rationale are required")
    if action == "override" and (replacement_score is None or not 0 <= replacement_score <= 100):
        raise ValueError("Override requires a replacement score from 0 to 100")
    if action != "override" and replacement_score is not None:
        raise ValueError("Replacement score is only valid for override")
    conn = connect(db_path)
    try:
        with conn:
            item = conn.execute("SELECT status,current_score FROM finding_status WHERE finding_id=?",
                                (finding_id,)).fetchone()
            if item is None:
                raise ValueError(f"Unknown finding: {finding_id}")
            new_score = replacement_score if replacement_score is not None else item["current_score"]
            new_status = {"confirm": "confirmed", "dismiss": "dismissed",
                          "override": "overridden"}[action]
            conn.execute("""INSERT INTO review_actions
                (finding_id, action, original_status, replacement_status, original_score,
                 replacement_score, actor, reason, acted_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                         (finding_id, action, item["status"], new_status, item["current_score"],
                          new_score, actor.strip(), reason.strip(), utc_now()))
        return {"finding_id": finding_id, "status": new_status, "score": new_score}
    finally:
        conn.close()
