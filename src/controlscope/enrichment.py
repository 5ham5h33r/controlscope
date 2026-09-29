"""Gemini may select evidence-backed facts; rendering stays deterministic."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .data import utc_now
from .store import connect, finding_detail

PROMPT_VERSION = "1.0.0"
STEPS = {
    "check_source": "Review the linked source rows and verify their source-system context.",
    "ask_owner": "Ask the control owner for the relevant approval or access rationale.",
    "compare_period": "Compare the same entity with adjacent audit periods.",
}


def facts_for_finding(item: dict) -> dict[str, str]:
    facts = {"finding": f"Control {item['control_id']} flagged {item['entity_type']} "
                        f"{item['entity_id']}: {item['detail']}"}
    for index, evidence in enumerate(item["evidence"], start=1):
        facts[f"e{index}"] = (
            f"Linked synthetic evidence row {evidence['table']}/{evidence['row_id']} "
            f"supports this finding."
        )
    return facts


def _select_with_gemini(facts: dict[str, str], model: str) -> dict:
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("Install the cloud extra: pip install -e '.[cloud]'") from exc
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for Gemini enrichment")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = (
        "Select up to 4 fact IDs that best explain this audit finding and up to 2 "
        "suggested review step IDs. Return only IDs from the provided lists. "
        "Do not infer a violation or add facts.\n"
        + json.dumps({"facts": facts, "steps": STEPS}, sort_keys=True)
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={"response_mime_type": "application/json",
                "response_schema": {"type": "OBJECT", "properties": {
                    "fact_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "step_ids": {"type": "ARRAY", "items": {"type": "STRING"}}},
                    "required": ["fact_ids", "step_ids"]}},
    )
    return json.loads(response.text)


def render_selection(facts: dict[str, str], selection: dict) -> dict:
    fact_ids = selection.get("fact_ids")
    step_ids = selection.get("step_ids")
    if not isinstance(fact_ids, list) or not isinstance(step_ids, list):
        raise ValueError("Enrichment must include fact_ids and step_ids lists")
    if not fact_ids or len(fact_ids) > 4 or len(step_ids) > 2:
        raise ValueError("Enrichment selection exceeds allowed bounds")
    if len(set(fact_ids)) != len(fact_ids) or len(set(step_ids)) != len(step_ids):
        raise ValueError("Duplicate enrichment IDs")
    if any(key not in facts for key in fact_ids) or any(key not in STEPS for key in step_ids):
        raise ValueError("Gemini referenced an ungrounded fact or step")
    return {
        "evidence_summary": [{"fact_id": key, "statement": facts[key]} for key in fact_ids],
        "suggested_review_steps": [{"step_id": key, "suggestion": STEPS[key]}
                                   for key in step_ids],
        "disclaimer": "Analyst review required; this is not a conclusion of fraud or violation.",
    }


def enrich(db_path: Path, finding_id: str, provider: str = "template",
           model: str = "gemini-2.5-flash") -> dict:
    if provider not in {"template", "gemini"}:
        raise ValueError("Provider must be template or gemini")
    conn = connect(db_path)
    try:
        item = finding_detail(conn, finding_id)
        facts = facts_for_finding(item)
        selection = ({"fact_ids": list(facts)[:4], "step_ids": ["check_source", "ask_owner"]}
                     if provider == "template" else _select_with_gemini(facts, model))
        content = render_selection(facts, selection)
        with conn:
            conn.execute("""INSERT OR REPLACE INTO enrichments VALUES (?,?,?,?,?,?)""",
                         (finding_id, provider, model if provider == "gemini" else "deterministic",
                          PROMPT_VERSION, json.dumps(content, sort_keys=True), utc_now()))
        return content
    finally:
        conn.close()
