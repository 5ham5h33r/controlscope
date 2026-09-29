"""Command line interface for the offline demo and optional cloud publication."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .data import write_dataset
from .enrichment import enrich
from .pipeline import review, run
from .store import connect, finding_detail, integrity_errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="controlscope")
    parser.add_argument("--db", type=Path, default=Path("data/controlscope.sqlite"))
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate", help="Write deterministic synthetic CSV data")
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 1, 31))
    generate.add_argument("--out", type=Path, default=Path("data/synthetic"))
    execute = sub.add_parser("run", help="Evaluate all controls")
    execute.add_argument("--data", type=Path, default=Path("data/synthetic"))
    demo = sub.add_parser("demo", help="Generate and run the offline demo")
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 1, 31))
    listing = sub.add_parser("findings", help="List findings")
    listing.add_argument("--run-id")
    detail = sub.add_parser("show", help="Show finding and linked evidence")
    detail.add_argument("finding_id")
    action = sub.add_parser("review", help="Append a reviewer decision")
    action.add_argument("finding_id")
    action.add_argument("action", choices=["confirm", "dismiss", "override"])
    action.add_argument("--actor", required=True)
    action.add_argument("--reason", required=True)
    action.add_argument("--score", type=int)
    enrichment = sub.add_parser("enrich", help="Add grounded explanation")
    enrichment.add_argument("finding_id")
    enrichment.add_argument("--provider", choices=["template", "gemini"], default="template")
    enrichment.add_argument("--model", default="gemini-2.5-flash")
    sub.add_parser("verify", help="Check evidence foreign keys and coverage")
    export = sub.add_parser("export", help="Write audit summary JSON")
    export.add_argument("--out", type=Path, default=Path("data/audit-summary.json"))
    dashboard = sub.add_parser("dashboard", help="Write a self-contained local dashboard")
    dashboard.add_argument("--out", type=Path, default=Path("data/dashboard.html"))
    upload = sub.add_parser("upload-bigquery", help="Load synthetic CSV source tables")
    upload.add_argument("--data", type=Path, default=Path("data/synthetic"))
    upload.add_argument("--project", required=True)
    upload.add_argument("--dataset", required=True)
    publish = sub.add_parser("publish-bigquery", help="Publish curated run tables")
    publish.add_argument("--project", required=True)
    publish.add_argument("--dataset", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate":
            result = {"dataset_sha256": write_dataset(args.out, args.seed, args.as_of)}
        elif args.command == "run":
            result = run(args.data, args.db)
        elif args.command == "demo":
            write_dataset(Path("data/synthetic"), args.seed, args.as_of)
            result = run(Path("data/synthetic"), args.db)
        elif args.command == "review":
            result = review(args.db, args.finding_id, args.action, args.actor,
                            args.reason, args.score)
        elif args.command == "enrich":
            result = enrich(args.db, args.finding_id, args.provider, args.model)
        elif args.command == "dashboard":
            from .dashboard import write_dashboard

            result = write_dashboard(args.db, args.out)
        elif args.command in {"findings", "show", "verify", "export"}:
            conn = connect(args.db)
            try:
                if args.command == "findings":
                    where = "WHERE run_id=?" if args.run_id else ""
                    params = (args.run_id,) if args.run_id else ()
                    result = [dict(row) for row in conn.execute(
                        f"SELECT finding_id,run_id,control_id,entity_id,business_unit,"
                        f"current_score,status FROM finding_status {where} "
                        f"ORDER BY current_score DESC, finding_id", params)]
                elif args.command == "show":
                    result = finding_detail(conn, args.finding_id)
                elif args.command == "verify":
                    errors = integrity_errors(conn)
                    result = {"ok": not errors, "errors": errors}
                else:
                    result = {
                        "runs": [json.loads(row[0]) for row in conn.execute(
                            "SELECT manifest_json FROM runs ORDER BY created_at")],
                        "findings": [finding_detail(conn, row[0]) for row in conn.execute(
                            "SELECT finding_id FROM findings ORDER BY finding_id")],
                    }
                    args.out.parent.mkdir(parents=True, exist_ok=True)
                    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                    result = {"exported": str(args.out), "findings": len(result["findings"])}
            finally:
                conn.close()
        elif args.command in {"upload-bigquery", "publish-bigquery"}:
            from .bigquery import publish_curated, upload_sources

            result = (upload_sources(args.data, args.project, args.dataset)
                      if args.command == "upload-bigquery"
                      else publish_curated(args.db, args.project, args.dataset))
        else:
            raise AssertionError(args.command)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
