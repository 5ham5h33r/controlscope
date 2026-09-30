# Dashboard guide and Looker Studio specification

[Public review workspace](https://5ham5h33r.github.io/controlscope/) · [Demo walkthrough](demo.md) · [Back to README](../README.md)

## Available dashboards

The public review workspace is a self-contained HTML snapshot hosted on GitHub Pages. It supports a prioritized queue, search and filters, readable source evidence, control coverage, and run details. It requires no sign-in. Generate a local copy with `controlscope dashboard` after completing the README setup.

A separate Looker Studio report was created on 2026-09-29 over the synthetic `controlscope-audit-2026.controlscope` BigQuery dataset. It is restricted to the report owner. The captures below allow repository visitors to inspect its current scope without requesting account access.

The report has four pages: Overview (11 findings, 6 high-risk findings, findings by control, current score histogram, status), Finding review (11 findings with control, entity, business unit, status, and score), Source evidence (33 source rows with a `finding_id` filter and JSON), and Run & control quality (all 10 registry controls and the published run ID and creation time). The report is read-only. The [public review workspace](https://5ham5h33r.github.io/controlscope/) shows the same synthetic snapshot with a prioritized queue, readable source fields, review history, and run lineage. Generate a local copy with `controlscope dashboard` after `controlscope demo`.

The live report is an MVP subset of the specification below. It does not yet show a review-action history, Gemini enrichments, age calculations, or individual fields inside `runs.manifest_json`. Data Studio interpreted `manifest_json` as a date in the direct connector, so the run table omits that field; inspect the raw BigQuery JSON or create a text-typed view before adding it. The currently published synthetic snapshot has no review actions or enrichments and only one run, so progress and run-trend comparisons cannot yet be demonstrated. The BigQuery project uses the sandbox; its tables may expire after 60 days unless billing is enabled and the data is republished. The connector and report currently load live data without linked billing.

The report account uses BigQuery Job User on the project and BigQuery Data Viewer on the synthetic dataset. Reproducing the report requires an account authorized for both queries and dataset reads.

## BigQuery sources

Connect Looker Studio to these tables in the `controlscope` dataset:

| Source | Use |
| --- | --- |
| `findings` | Run, control, business unit, risk, current status, and creation time |
| `evidence` | Finding-to-source-row drill-down, including JSON source row |
| `runs` | Manifest, run date, seed, dataset and code lineage |
| `review_actions` | Reviewer actions and override history |
| `enrichments` | Evidence-backed summaries and suggested steps |
| `mart_control_coverage` | Enabled controls, version, kind, and hit counts for current dbt input |

The curated `findings` table already includes `status` and `current_score`, derived from the latest review event. Join on `finding_id` for evidence/actions/enrichment, and `run_id` for run metadata. Use BigQuery views or Looker Studio blended data for these relationships. Keep `source_rows` access scoped to the synthetic demo dataset.

## Page 1: Overview

- Filters: `run_id`, `control_id`, `business_unit`, `status`, and risk band.
- Scorecards: total findings, open findings, high-risk findings, distinct controls with hits, and average finding age.
- Control coverage: bar chart by control with finding count, alongside all ten registry controls, including zero-hit controls.
- Risk distribution: stacked bars for high (80–100), medium (50–79), low (0–49) by control or business unit.
- Review progress: counts by `status` (`open`, `confirmed`, `dismissed`, `overridden`).
- Trend: findings by run creation date, split by risk band.

Calculate age as `DATE_DIFF(CURRENT_DATE(), DATE(created_at), DAY)` and use `current_score` for the risk band. Label the report **Synthetic demo — reviewer judgment required**.

## Page 2: Finding review

- Table: `finding_id`, run, control/version, entity, business unit, base risk, current score, status, creation date, age, and evidence count.
- Drill-down: click a finding to show all `evidence.table_name`, `evidence.row_id`, and `evidence.row_json` entries.
- Review panel: action history ordered by `action_id`, with actor, reason, timestamp, prior/replacement status, and prior/replacement score.
- Explanation: display `enrichments.content_json` after publication. Distinguish evidence statements from suggested review steps.
- Link back to the run manifest so a reviewer can inspect seed, dataset digest, code digest, registry digest, and versions.

Looker Studio is read-only for this MVP. Record decisions with the CLI and run `publish-bigquery` again to refresh the report.

## Page 3: Run and control quality

- Run table: run ID, creation time, seed, snapshot date, dataset hash, code hash, registry hash, and source row counts from `manifest_json`.
- Control table: control ID, version, kind, description, finding count, and high-risk count.
- Alert tile: count of findings without evidence should be zero; the local integrity gate and dbt singular test enforce this before publication.
- Compare runs by control/entity to see repeated exceptions. Only compare periods with the same control version or label version changes.

## Current report captures

These images were exported from the live report on 2026-09-29 and contain synthetic data only:

- [Overview](screenshots/overview.png)
- [Finding review](screenshots/finding-review.png)
- [Source evidence](screenshots/source-evidence.png)
- [Run & control quality](screenshots/run-control-quality.png)

They document the current report. The review history and full manifest views in the specification above are pending, so these captures do not demonstrate those workflows.
