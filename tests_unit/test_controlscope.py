import csv
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from controlscope.controls import evaluate, load_registry
from controlscope.data import dataset_hash, generate, read_dataset, write_dataset
from controlscope.enrichment import enrich, render_selection
from controlscope.pipeline import REGISTRY, review, run
from controlscope.store import connect, finding_detail, integrity_errors


class ControlScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "synthetic"
        self.db_path = self.root / "demo.sqlite"
        write_dataset(self.data_dir)

    def test_generation_is_repeatable_and_synthetic(self):
        first = generate(42, date(2026, 1, 31))
        second = generate(42, date(2026, 1, 31))
        self.assertEqual(dataset_hash(first), dataset_hash(second))
        self.assertEqual(first, read_dataset(self.data_dir))
        self.assertTrue(json.loads((self.data_dir / "dataset.json").read_text())["synthetic"])

    def test_every_control_exercised(self):
        hits = evaluate(read_dataset(self.data_dir))
        registry = load_registry(REGISTRY)
        self.assertEqual({r["id"] for r in registry["controls"]}, {h.control_id for h in hits})
        self.assertEqual(8, sum(r["kind"] == "deterministic" for r in registry["controls"]))
        self.assertEqual(2, sum(r["kind"] == "anomaly" for r in registry["controls"]))

    def test_run_evidence_and_reuse(self):
        first = run(self.data_dir, self.db_path)
        second = run(self.data_dir, self.db_path)
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertTrue(second["reused"])
        conn = connect(self.db_path)
        try:
            self.assertEqual([], integrity_errors(conn))
            self.assertEqual(first["findings"], conn.execute(
                "SELECT COUNT(*) FROM findings").fetchone()[0])
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE runs SET created_at='changed' WHERE run_id=?",
                             (first["run_id"],))
            for row in conn.execute("SELECT finding_id FROM findings"):
                self.assertGreater(len(finding_detail(conn, row[0])["evidence"]), 0)
        finally:
            conn.close()

    def test_review_override_is_append_only_with_originals(self):
        run(self.data_dir, self.db_path)
        conn = connect(self.db_path)
        finding_id = conn.execute("SELECT finding_id FROM findings LIMIT 1").fetchone()[0]
        initial = finding_detail(conn, finding_id)["risk_score"]
        conn.close()
        with self.assertRaises(ValueError):
            review(self.db_path, finding_id, "override", "reviewer", "", 20)
        result = review(self.db_path, finding_id, "override", "reviewer", "Verified approval", 20)
        self.assertEqual(20, result["score"])
        review(self.db_path, finding_id, "confirm", "manager", "Evidence checked")
        conn = connect(self.db_path)
        try:
            history = finding_detail(conn, finding_id)["review_history"]
            self.assertEqual([initial, 20], [row["original_score"] for row in history])
            self.assertEqual([20, 20], [row["replacement_score"] for row in history])
            self.assertEqual(["open", "overridden"], [row["original_status"] for row in history])
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM review_actions WHERE action_id=?", (history[0]["action_id"],))
        finally:
            conn.close()

    def test_enrichment_rejects_unsupported_content(self):
        with self.assertRaises(ValueError):
            render_selection({"f1": "Known fact"}, {"fact_ids": ["fabricated"], "step_ids": []})
        run(self.data_dir, self.db_path)
        conn = connect(self.db_path)
        finding_id = conn.execute("SELECT finding_id FROM findings LIMIT 1").fetchone()[0]
        conn.close()
        result = enrich(self.db_path, finding_id)
        self.assertTrue(result["evidence_summary"])
        conn = connect(self.db_path)
        try:
            item = finding_detail(conn, finding_id)
            self.assertEqual(result, item["enrichment"])
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM findings WHERE finding_id=?",
                                             (finding_id,)).fetchone()[0])
        finally:
            conn.close()

    def test_registry_matches_dbt_seed(self):
        registry = {r["id"]: r for r in load_registry(REGISTRY)["controls"]}
        with (REGISTRY.parents[1] / "seeds" / "control_registry.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(set(registry), {row["control_id"] for row in rows})
        for row in rows:
            self.assertEqual(registry[row["control_id"]]["version"], row["control_version"])
            self.assertEqual(registry[row["control_id"]]["base_risk"], int(row["base_risk"]))


if __name__ == "__main__":
    unittest.main()
