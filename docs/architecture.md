# Architecture and data contracts

## Trust boundary

ControlScope operates on synthetic records only. The generator marks each snapshot as synthetic in `dataset.json`; local runs and BigQuery upload reject a snapshot without that flag. This marker is a demo guard, not a reliable classification mechanism for production data. Do not attach real financial, HR, or identity feeds.

## Source tables

| Table | Key | Important columns |
| --- | --- | --- |
| `vendors` | `vendor_id` | `active`, `business_unit` |
| `users` | `user_id` | `employment_status`, `privileged`, `business_unit` |
| `transactions` | `transaction_id` | `vendor_id`, `invoice_id`, `amount`, `paid_at`, `initiator_id`, `approver_id` |
| `access_events` | `event_id` | `user_id`, `event_type`, `occurred_at` |

The generator fixes the seed and date and uses synthetic names and documentation-only IP addresses. Each CSV row is held under its table/key pair. The BigQuery `raw_*` tables are the current dbt input; the curated `source_rows` table keeps every published run's source-row snapshot.

## Run and finding lineage

`runs.manifest_json` records the dataset SHA-256, Python source digest, control registry digest, seed, date, Git commit, control versions, risk formula version, prompt version, source row counts, and creation timestamp. The run ID is a digest of the stable inputs, so re-running unchanged inputs reuses the run. Uncommitted changes are represented by the source digest even if the Git commit is unchanged.

`findings` contains a stable finding ID, run ID, control ID/version, entity ID, business unit, rule detail, base risk, and initial risk score. `evidence` contains table/key references. Its composite foreign key points at `source_rows` in the same run. Each finding must have at least one evidence row; `controlscope verify` checks this and all foreign keys.

Local SQLite `review_actions` contains action, prior and new status, prior and new score, actor, timestamp, and required rationale. Its update/delete triggers enforce append-only decisions. The `finding_status` view derives current status and score from the latest action. A later action never rewrites the original finding.

`enrichments` stores provider, model, prompt version, and rendered content. The renderer only accepts fact IDs supplied from the finding and step IDs from a fixed allowlist. The model cannot add finding rows, alter risk, or insert unsupported narrative claims.

## BigQuery and dbt

BigQuery ingestion loads the four synthetic CSV tables into `raw_*`. dbt models use the following layers:

- `stg_*`: typed source interfaces and key/relationship tests.
- `int_payment_groups`, `int_access_activity`: reusable aggregations.
- `int_control_hits`, `int_anomaly_hits`: warehouse implementations of the eight fixed checks and two robust detectors.
- `mart_findings`, `mart_control_coverage`: scored findings and per-control coverage.

The local engine uses exact Python medians. The warehouse uses BigQuery `PERCENTILE_CONT` for exact medians and MADs. Minor numeric representation differences at a threshold remain a risk; synthetic scenarios are placed comfortably beyond thresholds. The dbt mart finding ID is a warehouse-local hash of its control, entity, and evidence; the local run finding ID also includes run identity. Compare controls/entities/evidence when reconciling the two implementations.

`publish-bigquery` copies the reviewed local records into BigQuery tables `runs`, `source_rows`, `findings`, `evidence`, `review_actions`, and `enrichments`. It truncates and reloads those tables as a complete snapshot, while retaining all runs and append-only decisions from the local store. It checks evidence integrity before publication.

## Detector thresholds

The payment amount detector computes a median and median absolute deviation (MAD) within each business unit and flags robust z-scores above 6. The login burst detector compares each user's daily event count with the median and MAD across user-days, requires at least eight extra logins above the baseline, and flags a robust score above 6 or a zero-MAD baseline. These thresholds are demonstrated on injected synthetic scenarios; they have not been calibrated against production false-positive rates.

## Tests and limits

Unit tests cover determinism, all ten injected scenarios, registry parity, evidence links, run reuse, required review rationale, append-only triggers, and rejection of unsupported enrichment IDs. dbt tests check source keys/relationships, mart keys, all controls exercised, and evidence references. Live dbt execution, Gemini calls, and Looker Studio publication require cloud credentials and are not part of the offline validation.

The demo does not provide production security controls, data retention rules, role-based access, scheduling, or legal interpretation. Review actions use a caller-supplied actor string; identity verification is a post-MVP concern.
