# ARTSTUDIO GitHub-Native Control Runbook

## 0. What The Workflow Does

`GitHub-native Drive Ops` is the operational wrapper for the preparation stage.

Current commands:

- `validate-readiness`: checks canonical folders, control files, runtime policy and writes validation output.
- `plan-reorganization`: scans accessible Drive files, classifies project-related materials and writes recommendations into `ARTSTUDIO_Reorganization_Plan`.
- `prepare-and-plan`: creates missing structure, merges duplicate root folders, then writes the reorganization plan.
- `complete-prep`: creates missing structure, merges duplicate root folders, plans moves, executes auto-safe rows, validates readiness and logs the run.
- `execute-safe-actions`: executes already planned rows in `ARTSTUDIO_Reorganization_Plan`.
- `prepare-structure`: only creates missing canonical folders. It does not classify or move existing files.

`dry_run = true` means no Drive or Sheet writes. Use it only to inspect the JSON summary in the workflow run. To change Drive, run with `dry_run = false`.

## 1. Access Setup

1. Create or choose a Google Cloud service account.
2. Enable Google Drive API, Google Sheets API and Google Docs API for the service account project.
3. Add the full service account JSON as GitHub secret `GOOGLE_SERVICE_ACCOUNT_JSON`.
4. Share the ARTSTUDIO root folder and `00_CONTROL_CENTER` with the service account email as Editor.
5. Share any project files that currently sit outside ARTSTUDIO with the service account, or move them into ARTSTUDIO manually before automation.
6. Confirm nested folders/files inherit permissions or are explicitly shared.

The workflow cannot reorganize files it cannot see. Files in the user's My Drive root are visible only if they are shared with the service account or already under a shared folder.

## 2. Repository Validation

Run GitHub Actions workflow `Validate knowledge ops`.

Expected result:

- JSON config parses;
- Python modules compile;
- required docs/config/workflows exist;
- runtime is `github_actions_service_account`;
- permanent delete is disabled;
- preparation commands are present.

## 3. Discovery Dry Run

Run `GitHub-native Drive Ops`:

- `command = plan-reorganization`
- `dry_run = true`

Expected result:

- workflow authenticates with the service account;
- Drive and Sheets APIs are reachable;
- JSON summary appears in the workflow run summary;
- no Drive/Sheet writes are made.

If this finds zero project files while the user's Drive clearly has ARTSTUDIO files outside the ARTSTUDIO folder, the service account lacks access to those outside files.

## 4. Write The Plan

Run `GitHub-native Drive Ops`:

- `command = plan-reorganization`
- `dry_run = false`

Expected result:

- `Preparation Recommendations` tab is refreshed in `ARTSTUDIO_Reorganization_Plan`;
- executable low-risk move rows are appended to `Main`;
- uncertain items are marked for human review;
- Tool Run Log receives a planning entry.

## 5. Complete Preparation

Run `GitHub-native Drive Ops`:

- `command = complete-prep`
- `dry_run = false`

Expected result:

- missing canonical folders are created;
- duplicate root folders are merged into the canonical folder;
- empty duplicate folders are moved to Drive trash, not permanently deleted;
- accessible project-related files are moved to the target canonical section;
- `Native GitHub Validation`, `Folder Duplicate Audit` and `Preparation Recommendations` are refreshed;
- Tool Run Log receives entries for each stage.

## 6. Human Review Rows

Review remaining rows in `ARTSTUDIO_Reorganization_Plan`.

Use these values:

- `Human decision = accepted` for human-approved actions;
- `Human decision = auto-safe` for low-risk policy-approved rows;
- `Human decision = rejected` for actions that must not run;
- `Human decision = needs discussion` for ambiguous rows;
- `Safe action = trash duplicate` only when the duplicate is obvious;
- `Safe action = no automated action` when the action should remain manual.

Then run:

- `command = execute-safe-actions`
- `dry_run = false`

## 7. Final Validation

Run `GitHub-native Drive Ops`:

- `command = validate-readiness`
- `dry_run = false`

Expected result:

- canonical folders exist exactly as configured;
- control files exist;
- validation sheet `Native GitHub Validation` is refreshed;
- duplicate root folders are no longer present;
- Tool Run Log has GitHub-native execution entries.

## 8. Transition To Internal Audit

After validation passes:

1. Use `ARTSTUDIO_Source_Map` and `ARTSTUDIO_Master_Index` as the intake ledger.
2. Start with files now in `01_INBOX` plus newly sorted files in canonical sections.
3. Produce a gap list by section: brand, object data, SOP, official sites, OTA, reviews, legal, owner/investor and market.
4. Use Intake, Catalog, QA, Docs and Governance agent specs to classify, summarize, detect contradictions and recommend missing materials.
