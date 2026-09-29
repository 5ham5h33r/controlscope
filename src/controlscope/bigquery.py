"""Optional BigQuery ingestion and curated snapshot publication."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .data import TABLE_FIELDS
from .store import connect, integrity_errors

SOURCE_TYPES = {
    "vendors": {"active": "BOOLEAN"},
    "users": {"privileged": "BOOLEAN"},
    "transactions": {"amount": "NUMERIC", "paid_at": "TIMESTAMP"},
    "access_events": {"occurred_at": "TIMESTAMP"},
}

CURATED_TYPES = {
    "runs": {"created_at": "TIMESTAMP"},
    "source_rows": {},
    "findings": {"base_risk": "INTEGER", "risk_score": "INTEGER",
                 "current_score": "INTEGER", "created_at": "TIMESTAMP"},
    "evidence": {},
    "review_actions": {"action_id": "INTEGER", "original_score": "INTEGER",
                       "replacement_score": "INTEGER", "acted_at": "TIMESTAMP"},
    "enrichments": {"created_at": "TIMESTAMP"},
}


def _client(project: str, dataset: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*", dataset
    ):
        raise ValueError("Invalid BigQuery project or dataset identifier")
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise RuntimeError("Install the cloud extra: pip install -e '.[cloud]'") from exc
    client = bigquery.Client(project=project)
    client.create_dataset(bigquery.Dataset(f"{project}.{dataset}"), exists_ok=True)
    return bigquery, client


def upload_sources(data_dir: Path, project: str, dataset: str) -> dict:
    meta = json.loads((data_dir / "dataset.json").read_text(encoding="utf-8"))
    if meta.get("synthetic") is not True:
        raise ValueError("Only synthetic data can be uploaded by this demo")
    bigquery, client = _client(project, dataset)
    counts = {}
    for table, fields in TABLE_FIELDS.items():
        schema = [bigquery.SchemaField(field, SOURCE_TYPES.get(table, {}).get(field, "STRING"))
                  for field in fields]
        config = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.CSV,
                                        skip_leading_rows=1, schema=schema,
                                        write_disposition="WRITE_TRUNCATE")
        with (data_dir / f"{table}.csv").open("rb") as handle:
            job = client.load_table_from_file(handle, f"{project}.{dataset}.raw_{table}",
                                              job_config=config)
            job.result()
        counts[table] = client.get_table(f"{project}.{dataset}.raw_{table}").num_rows
    return {"dataset": f"{project}.{dataset}", "source_rows": counts}


def publish_curated(db_path: Path, project: str, dataset: str) -> dict:
    bigquery, client = _client(project, dataset)
    conn = connect(db_path)
    try:
        errors = integrity_errors(conn)
        if errors:
            raise ValueError(f"Evidence integrity failed: {errors}")
        source = {
            "runs": "SELECT run_id,created_at,manifest_json FROM runs",
            "source_rows": "SELECT * FROM source_rows",
            "findings": "SELECT * FROM finding_status",
            "evidence": """SELECT e.finding_id,e.run_id,e.table_name,e.row_id,s.row_json
                           FROM evidence e JOIN source_rows s USING (run_id,table_name,row_id)""",
            "review_actions": "SELECT * FROM review_actions",
            "enrichments": "SELECT * FROM enrichments",
        }
        counts = {}
        for table, query in source.items():
            cursor = conn.execute(query)
            fields = [col[0] for col in cursor.description]
            rows = [dict(row) for row in cursor]
            schema = [bigquery.SchemaField(field, CURATED_TYPES[table].get(field, "STRING"))
                      for field in fields]
            # Empty tables still need a schema so the dashboard can bind to them.
            config = bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE")
            table_id = f"{project}.{dataset}.{table}"
            if rows:
                job = client.load_table_from_json(rows, table_id, job_config=config)
                job.result()
            else:
                client.delete_table(table_id, not_found_ok=True)
                client.create_table(bigquery.Table(table_id, schema=schema))
            counts[table] = len(rows)
        return {"dataset": f"{project}.{dataset}", "curated_rows": counts}
    finally:
        conn.close()
