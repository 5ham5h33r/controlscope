# Deployment record

| Resource | Value | Status |
| --- | --- | --- |
| Google Cloud project | `controlscope-audit-2026` | Created 2026-09-28 |
| BigQuery dataset | `controlscope-audit-2026.controlscope` | Created in US multi-region |
| Billing | Not linked | BigQuery sandbox; tables expire after 60 days |
| Raw source tables | Pending cloud upload | Local synthetic CSVs are generated |
| dbt models and tests | Parsed locally | Live execution pending cloud upload |
| Looker Studio | Pending billing and data | [Specification](dashboard.md) and local HTML preview available |

The project and dataset were created in the user's Google Cloud account for the synthetic demo. No account credentials or API keys are stored in this repository. Run `scripts/deploy_cloud_shell.sh controlscope-audit-2026 controlscope` from an authorized Cloud Shell after transferring the repository, or use the commands in the [README](../README.md) from a machine with Application Default Credentials.
