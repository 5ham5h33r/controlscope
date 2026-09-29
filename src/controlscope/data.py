"""Deterministic synthetic source data with deliberate control scenarios."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TABLE_FIELDS = {
    "vendors": ["vendor_id", "vendor_name", "active", "business_unit"],
    "users": ["user_id", "user_name", "employment_status", "privileged", "business_unit"],
    "transactions": [
        "transaction_id", "vendor_id", "invoice_id", "amount", "currency", "business_unit",
        "initiator_id", "approver_id", "paid_at", "payment_status",
    ],
    "access_events": ["event_id", "user_id", "event_type", "occurred_at", "source_ip"],
}


def generate(seed: int = 42, as_of: date = date(2026, 1, 31)) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    vendors = [
        {"vendor_id": f"V{i:03}", "vendor_name": f"Synthetic Vendor {i:03}",
         "active": "false" if i == 12 else "true", "business_unit": "Finance" if i % 2 else "IT"}
        for i in range(1, 13)
    ]
    users = [
        {"user_id": f"U{i:03}", "user_name": f"Synthetic User {i:03}",
         "employment_status": "terminated" if i == 12 else "active",
         "privileged": "true" if i in (10, 11) else "false",
         "business_unit": "Finance" if i % 2 else "IT"}
        for i in range(1, 13)
    ]
    transactions = []
    for i in range(1, 121):
        day = as_of - timedelta(days=rng.randrange(0, 28))
        transactions.append({
            "transaction_id": f"T{i:04}", "vendor_id": f"V{rng.randrange(1, 11):03}",
            "invoice_id": f"INV-{i:04}", "amount": f"{rng.randrange(100, 3800)}.00",
            "currency": "USD", "business_unit": "Finance" if i % 2 else "IT",
            "initiator_id": f"U{rng.randrange(1, 9):03}",
            "approver_id": f"U{rng.randrange(9, 11):03}",
            "paid_at": f"{day.isoformat()}T14:00:00+00:00", "payment_status": "paid",
        })

    def tx(n: int, **overrides: str) -> None:
        row = {
            "transaction_id": f"T{n:04}", "vendor_id": "V001", "invoice_id": f"INV-{n:04}",
            "amount": "1200.00", "currency": "USD", "business_unit": "Finance",
            "initiator_id": "U001", "approver_id": "U009",
            "paid_at": f"{as_of.isoformat()}T14:00:00+00:00", "payment_status": "paid",
        }
        row.update(overrides)
        transactions.append(row)

    tx(121, invoice_id="DUP-01", amount="1900.00")
    tx(122, invoice_id="DUP-01", amount="1900.00")
    tx(123, vendor_id="V002", amount="6000.00")
    tx(124, vendor_id="V002", amount="6500.00")
    tx(125, paid_at=f"{as_of.isoformat()}T02:00:00+00:00")
    tx(126, vendor_id="V012")
    tx(127, approver_id="U001")
    tx(128, amount="30000.00", approver_id="")
    tx(129, amount="99000.00")

    access_events = []
    for i in range(1, 101):
        day = as_of - timedelta(days=rng.randrange(0, 28))
        access_events.append({
            "event_id": f"E{i:04}", "user_id": f"U{rng.randrange(1, 10):03}",
            "event_type": "login", "occurred_at": f"{day.isoformat()}T16:00:00+00:00",
            "source_ip": "192.0.2.10",
        })
    access_events.append({"event_id": "E0101", "user_id": "U012", "event_type": "login",
                          "occurred_at": f"{as_of.isoformat()}T16:00:00+00:00",
                          "source_ip": "192.0.2.11"})
    access_events.append({"event_id": "E0102", "user_id": "U011", "event_type": "login",
                          "occurred_at": f"{as_of.isoformat()}T16:00:00+00:00",
                          "source_ip": "192.0.2.12"})
    access_events.append({"event_id": "E0119", "user_id": "U011", "event_type": "login",
                          "occurred_at": f"{(as_of - timedelta(days=35)).isoformat()}T16:00:00+00:00",
                          "source_ip": "192.0.2.12"})
    for i in range(103, 119):
        access_events.append({"event_id": f"E{i:04}", "user_id": "U003",
                              "event_type": "login",
                              "occurred_at": f"{as_of.isoformat()}T16:{i % 60:02}:00+00:00",
                              "source_ip": "192.0.2.13"})
    return {"vendors": vendors, "users": users, "transactions": transactions,
            "access_events": access_events}


def write_dataset(directory: Path, seed: int = 42, as_of: date = date(2026, 1, 31)) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    dataset = generate(seed, as_of)
    for table, rows in dataset.items():
        with (directory / f"{table}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=TABLE_FIELDS[table], lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    (directory / "dataset.json").write_text(
        json.dumps({"seed": seed, "as_of": as_of.isoformat(), "synthetic": True}, indent=2) + "\n",
        encoding="utf-8",
    )
    return dataset_hash(dataset)


def read_dataset(directory: Path) -> dict[str, list[dict]]:
    dataset = {}
    for table in TABLE_FIELDS:
        with (directory / f"{table}.csv").open(newline="", encoding="utf-8") as handle:
            dataset[table] = list(csv.DictReader(handle))
    return dataset


def dataset_hash(dataset: dict[str, list[dict]]) -> str:
    payload = json.dumps(dataset, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
