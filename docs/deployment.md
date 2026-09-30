# Deployment record

| Resource | Value | Status |
| --- | --- | --- |
| Google Cloud project | `controlscope-audit-2026` | Created 2026-09-28 |
| BigQuery dataset | `controlscope-audit-2026.controlscope` | Created in US multi-region |
| Billing | Not linked | BigQuery sandbox; tables expire after 60 days |
| Raw source tables | Published | Four `raw_*` tables contain the synthetic snapshot |
| dbt models and tests | Published and passed | Staging and intermediate views plus finding and coverage marts; 17 of 17 dbt tests passed |
| Curated audit tables | Published | 1 run, 272 source rows, 11 findings, and 33 evidence links |
| Looker Studio | Live report created 2026-09-29 | Owned by the report-owning Google account; four report pages read the synthetic BigQuery dataset. See [scope and gaps](dashboard.md). |

The project and dataset were created in the user's Google Cloud account for the synthetic demo. On 2026-09-28 (Pacific time), the Cloud Shell deployment completed successfully in `controlscope-audit-2026.controlscope`. No account credentials or API keys are stored in this repository. To reproduce it, run `scripts/deploy_cloud_shell.sh controlscope-audit-2026 controlscope` from an authorized Cloud Shell after transferring the repository, or use the commands in the [README](../README.md) from a machine with Application Default Credentials.
