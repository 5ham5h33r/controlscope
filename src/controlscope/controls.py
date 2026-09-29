"""Local deterministic controls and robust anomaly detectors."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    control_id: str
    entity_type: str
    entity_id: str
    evidence: tuple[tuple[str, str], ...]
    detail: str
    business_unit: str


def load_registry(path: Path) -> dict:
    registry = json.loads(path.read_text(encoding="utf-8"))
    ids = [row["id"] for row in registry["controls"]]
    if len(ids) != len(set(ids)) or len(ids) != 10:
        raise ValueError("Control registry requires 10 unique controls")
    return registry


def evaluate(dataset: dict[str, list[dict]]) -> list[Candidate]:
    vendors = {row["vendor_id"]: row for row in dataset["vendors"]}
    users = {row["user_id"]: row for row in dataset["users"]}
    transactions = [r for r in dataset["transactions"] if r["payment_status"] == "paid"]
    events = [r for r in dataset["access_events"] if r["event_type"] == "login"]
    results: list[Candidate] = []

    def add(control: str, entity_type: str, entity_id: str, refs: list[tuple[str, str]],
            detail: str, unit: str) -> None:
        results.append(Candidate(control, entity_type, entity_id,
                                 tuple(sorted(set(refs))), detail, unit))

    invoices = defaultdict(list)
    payments = defaultdict(list)
    for tx in transactions:
        invoices[(tx["vendor_id"], tx["invoice_id"])].append(tx)
        day = tx["paid_at"][:10]
        if float(tx["amount"]) < 10000:
            payments[(tx["vendor_id"], day)].append(tx)
        tx_ref = [("transactions", tx["transaction_id"])]
        if int(tx["paid_at"][11:13]) < 6 or int(tx["paid_at"][11:13]) >= 22:
            add("off_hours_payment", "transaction", tx["transaction_id"], tx_ref,
                "Payment time falls outside 06:00-22:00 UTC.", tx["business_unit"])
        vendor = vendors[tx["vendor_id"]]
        if vendor["active"] == "false":
            add("inactive_vendor_payment", "transaction", tx["transaction_id"],
                tx_ref + [("vendors", vendor["vendor_id"])],
                "Vendor is inactive at this dataset snapshot.", tx["business_unit"])
        if tx["approver_id"] and tx["initiator_id"] == tx["approver_id"]:
            add("self_approval", "transaction", tx["transaction_id"], tx_ref,
                "Initiator and approver IDs match.", tx["business_unit"])
        if float(tx["amount"]) > 25000 and not tx["approver_id"]:
            add("missing_high_value_approval", "transaction", tx["transaction_id"], tx_ref,
                "Amount exceeds USD 25,000 with no approver ID.", tx["business_unit"])

    for (vendor_id, invoice_id), rows in invoices.items():
        if len(rows) > 1:
            refs = [("transactions", r["transaction_id"]) for r in rows]
            add("duplicate_invoice", "invoice", f"{vendor_id}:{invoice_id}", refs,
                f"{len(rows)} paid rows share this vendor and invoice ID.",
                rows[0]["business_unit"])
    for (vendor_id, day), rows in payments.items():
        total = sum(float(r["amount"]) for r in rows)
        if len(rows) > 1 and total >= 10000:
            refs = [("transactions", r["transaction_id"]) for r in rows]
            add("split_payment", "vendor_day", f"{vendor_id}:{day}", refs,
                f"{len(rows)} sub-USD 10,000 payments total USD {total:.2f}.",
                rows[0]["business_unit"])

    by_user = defaultdict(list)
    by_user_day = defaultdict(list)
    for event in events:
        user = users[event["user_id"]]
        ref = [("access_events", event["event_id"]), ("users", user["user_id"])]
        if user["employment_status"] == "terminated":
            add("terminated_user_login", "access_event", event["event_id"], ref,
                "User employment status is terminated.", user["business_unit"])
        by_user[event["user_id"]].append(event)
        by_user_day[(event["user_id"], event["occurred_at"][:10])].append(event)
    for user_id, rows in by_user.items():
        if users[user_id]["privileged"] != "true":
            continue
        ordered = sorted(rows, key=lambda r: (r["occurred_at"], r["event_id"]))
        for prior, current in zip(ordered, ordered[1:]):
            gap = datetime.fromisoformat(current["occurred_at"]) - datetime.fromisoformat(
                prior["occurred_at"])
            if gap >= timedelta(days=30):
                refs = [("access_events", prior["event_id"]),
                        ("access_events", current["event_id"]), ("users", user_id)]
                add("dormant_privileged_login", "access_event", current["event_id"], refs,
                    f"Privileged user had {gap.days} days between logins.",
                    users[user_id]["business_unit"])

    # Median absolute deviation is robust to the deliberately injected outlier.
    by_unit = defaultdict(list)
    for tx in transactions:
        by_unit[tx["business_unit"]].append(float(tx["amount"]))
    for tx in transactions:
        values = by_unit[tx["business_unit"]]
        median = statistics.median(values)
        mad = statistics.median(abs(value - median) for value in values)
        score = 0 if mad == 0 else 0.6745 * (float(tx["amount"]) - median) / mad
        if score > 6:
            add("amount_outlier", "transaction", tx["transaction_id"],
                [("transactions", tx["transaction_id"])],
                f"Amount robust z-score {score:.2f}; unit median USD {median:.2f}.",
                tx["business_unit"])

    daily_counts = [len(rows) for rows in by_user_day.values()]
    baseline = statistics.median(daily_counts) if daily_counts else 0
    mad = statistics.median(abs(n - baseline) for n in daily_counts) if daily_counts else 0
    for (user_id, day), rows in by_user_day.items():
        count = len(rows)
        robust_score = 0 if mad == 0 else 0.6745 * (count - baseline) / mad
        if count >= baseline + 8 and (mad == 0 or robust_score > 6):
            add("login_burst", "user_day", f"{user_id}:{day}",
                [("access_events", r["event_id"]) for r in rows],
                f"{count} logins versus daily median {baseline:g}.",
                users[user_id]["business_unit"])
    return sorted(results, key=lambda r: (r.control_id, r.entity_id, r.evidence))
