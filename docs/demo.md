# Demo walkthrough

[Open the public demo](https://5ham5h33r.github.io/controlscope/) · [Back to README](../README.md)

## Two-minute browser tour

No sign-in is needed. The public site contains synthetic data with snapshot date `2026-01-31`.

1. **Prioritize.** On Overview, note the 11 findings and six high-priority findings awaiting review. Open **Terminated user login** at the top of the queue.
2. **Inspect evidence.** Read the control rationale and the linked employee and access-event fields. The source records let you inspect why the rule fired. The finding is a review lead, not a conclusion about misconduct.
3. **Narrow the queue.** Close the detail panel, open Findings, and try a search or priority/control filter. Clear the filters to restore the full list.
4. **Check coverage.** Open Controls to inspect the eight rules and two statistical detectors, including each control's description and version. Selecting a control opens its findings.
5. **Check reproducibility.** Open Run details to inspect the snapshot's manifest and recorded lineage.

The public site is a read-only snapshot. Its source data and counts stay fixed until a new snapshot is published. Review commands shown in a finding's detail panel target the local CLI; the page does not submit decisions.

## Complete a local review

First run the [local setup](../README.md#run-locally). Run `controlscope findings` and copy a finding ID from your own run. IDs depend on the run inputs, so an ID copied from the published website may not exist in your local database.

Inspect it before choosing a decision:

```bash
controlscope show FINDING_ID
```

Choose one action based on the evidence. These are alternative examples, not a sequence to apply blindly to the same finding:

```bash
controlscope review FINDING_ID confirm --actor analyst@example.test --reason "Matched the supporting records"
controlscope review FINDING_ID dismiss --actor analyst@example.test --reason "Approved test transaction"
controlscope review FINDING_ID override --score 35 --actor analyst@example.test --reason "Compensating control verified"
```

Each action requires an actor and rationale. An override also requires a score from 0 to 100. The system appends the decision with its prior and replacement values; it does not rewrite the original finding. The actor is a supplied string, not an authenticated identity.

Generate an explanation, export the audit record, and refresh the dashboard:

```bash
controlscope enrich FINDING_ID
controlscope export
controlscope dashboard
controlscope verify
```

Open or refresh `data/dashboard.html`, then inspect the finding's status, score, and review history. `data/audit-summary.json` contains the export. The default explanation provider uses local templates; optional Gemini setup is in the [deployment guide](deployment.md).

## Reproduce or change a snapshot

The default run uses seed `42` and date `2026-01-31`. Repeating a run with unchanged data, Python source, and registry reuses its run ID and preserves review history. The manifest records digests, Git commit, seed, date, control versions, and risk formula version.

To create another snapshot:

```bash
controlscope generate --seed 7 --as-of 2026-02-28
controlscope run
controlscope dashboard
```

The database retains earlier runs; the dashboard presents the latest run. `data/` is ignored by Git because it contains generated artifacts. Publishing reviewed records to BigQuery and updating the public website are separate steps; local review commands do not update either remote surface automatically.
