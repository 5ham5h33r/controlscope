# Cloud deployment and recorded results

[Back to README](../README.md) · [Public demo](https://5ham5h33r.github.io/controlscope/)

## Recorded deployment

The entries below record the September 2026 deployment. They are not a live availability check. The public HTML demo is hosted separately on GitHub Pages and does not query BigQuery.

| Resource | Value | Status |
| --- | --- | --- |
| Google Cloud project | `controlscope-audit-2026` | Created 2026-09-28 |
| BigQuery dataset | `controlscope-audit-2026.controlscope` | Created in US multi-region |
| Billing | Not linked | BigQuery sandbox; tables expire after 60 days |
| Raw source tables | Published | Four `raw_*` tables contain the synthetic snapshot |
| dbt models and tests | Published and passed | Staging and intermediate views plus finding and coverage marts; 17 of 17 dbt tests passed |
| Curated audit tables | Published | 1 run, 272 source rows, 11 findings, and 33 evidence links |
| Looker Studio | Live report created 2026-09-29 | Owned by the report-owning Google account; four report pages read the synthetic BigQuery dataset. See [scope and gaps](dashboard.md). |

On 2026-09-28 (Pacific time), the Cloud Shell deployment completed successfully in `controlscope-audit-2026.controlscope`. No account credentials or API keys are stored in this repository. To reproduce it, follow the setup below or run `bash scripts/deploy_cloud_shell.sh YOUR_PROJECT controlscope` from an authorized Cloud Shell after cloning the repository.

## Reproduce in your own project

Clone the repository and complete the local setup in the [README](../README.md) first. Replace `YOUR_PROJECT` with a project you can access. Run commands from the repository root.

Install cloud dependencies and configure [Application Default Credentials](https://cloud.google.com/docs/authentication/provide-credentials-adc) with access to a BigQuery project. Costs and quota depend on your Google Cloud account.

```bash
python -m pip install -e ".[cloud]"
controlscope generate
controlscope run
controlscope upload-bigquery --project YOUR_PROJECT --dataset controlscope
cp profiles.example.yml profiles.yml  # edit project and authentication settings
dbt seed --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
controlscope publish-bigquery --project YOUR_PROJECT --dataset controlscope
```

On Windows PowerShell, use `Copy-Item profiles.example.yml profiles.yml` instead of `cp`. The upload creates `raw_*` BigQuery tables; dbt creates staging views, intermediate views, and finding/coverage marts. Publication copies versioned runs, all source-row snapshots, findings, evidence, review actions, and enrichment to curated BigQuery tables for reporting. Rerun `publish-bigquery` after reviewer actions. The local SQLite file is the offline working store; the cloud dataset holds the published analytical record.

For Google Cloud Shell, [scripts/deploy_cloud_shell.sh](../scripts/deploy_cloud_shell.sh) performs the same sequence after the repository is available there: `bash scripts/deploy_cloud_shell.sh YOUR_PROJECT controlscope`.

To request Gemini enrichment, set `GEMINI_API_KEY` in your environment and run:

```bash
controlscope enrich FINDING_ID --provider gemini --model gemini-2.5-flash
```

Gemini receives only the derived rule detail and synthetic evidence references, never full source rows, names, or IP addresses. It can only select fact IDs and suggested review-step IDs. ControlScope validates every returned ID and renders the final text from known facts and a fixed step list. A rejected response cannot alter the finding or evidence. The default `template` provider gives the same grounded format without a key. Prompt and model versions are recorded with enrichment.

## CI configuration

The optional cloud job uses the `GCP_SERVICE_ACCOUNT_JSON` repository secret and the `GCP_PROJECT` / `GCP_DATASET` repository variables. Without them, the integration step reports that it was skipped. Python checks and SQL linting/parsing still run in the local job.

Looker Studio access is separate from the public demo. See the [dashboard guide](dashboard.md) for data sources, report captures, and current feature gaps. The current cloud snapshot has one run and no published reviewer actions or enrichments; use the local walkthrough to exercise those features before republishing.
