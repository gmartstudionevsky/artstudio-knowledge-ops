# ARTSTUDIO GitHub-Native Control Runbook

## 0. Access Setup

1. Create or choose a Google Cloud service account.
2. Enable Google Drive API, Google Sheets API and Google Docs API for the service account project.
3. Add the full service account JSON as GitHub secret `GOOGLE_SERVICE_ACCOUNT_JSON`.
4. Share the ARTSTUDIO root folder and `00_CONTROL_CENTER` with the service account email as Editor.
5. Confirm nested folders/files inherit permissions or are explicitly shared.

See `docs/secrets.md` for optional secrets.

## 1. Validate Repository

Run GitHub Actions workflow `Validate knowledge ops`.

Expected result:

- JSON config parses;
- Python runtime compiles;
- required docs/config/workflows exist;
- runtime is `github_actions_service_account`;
- permanent delete is disabled.

## 2. Dry-Run Readiness

Run `GitHub-native Drive Ops`:

- `command = validate-readiness`
- `dry_run = true`

Expected result:

- workflow authenticates with the service account;
- Drive and Sheets APIs are reachable;
- no writes are made.

## 3. Current Legacy Structure Pass

Run `GitHub-native Drive Ops`:

- `command = execute-safe-actions`
- first `dry_run = true`
- then `dry_run = false` only if dry-run output is clean

The Reorganization Plan already contains accepted rows for creating `01_INBOX` and `03_Object_Data` and for renaming legacy root folders into the new numbering.

This pass should run before `prepare-structure`; otherwise empty target folders may be created before old populated folders are renamed.

## 4. Prepare Missing Structure

Run `GitHub-native Drive Ops`:

- `command = prepare-structure`
- `dry_run = false`

Expected result:

- any still-missing canonical folders are created under ARTSTUDIO;
- `98_Project_Methodology` and `99_Setup_Archive` are created inside `00_CONTROL_CENTER`;
- Tool Run Log receives a GitHub-native preparation entry.

## 5. Review Reorganization Plan

Review new or remaining rows in `ARTSTUDIO_Reorganization_Plan`.

Use these values:

- `Human decision = accepted` for human-approved actions;
- `Human decision = auto-safe` for low-risk policy-approved rows;
- `Human decision = rejected` for actions that must not run;
- `Human decision = needs discussion` for ambiguous rows;
- `Safe action = trash duplicate` only when the duplicate is obvious;
- `Safe action = no automated action` when the action should remain manual.

## 6. Execute Safe Actions Again

Run `GitHub-native Drive Ops` with `command = execute-safe-actions` after review if new executable rows exist.

The native runtime executes rows when either:

- `Human decision = accepted`; or
- `Human decision = auto-safe`, `Risk` is not high and `Safe action` is in the allowed safe-action set.

Supported execution actions:

- create folder;
- move file;
- move folder;
- rename file;
- rename folder;
- archive setup artifact;
- move methodology file;
- trash duplicate.

Permanent delete is never used.

## 7. Final Validation

Run `GitHub-native Drive Ops`:

- `command = validate-readiness`
- `dry_run = false`

Expected result:

- canonical folders exist;
- control files exist;
- validation sheet `Native GitHub Validation` is refreshed;
- Tool Run Log has entries for GitHub-native execution.

## 8. Transition To Filling The Base

After validation passes:

1. Move existing unclassified materials into `01_INBOX` or confirm their current canonical folder.
2. Use Intake/Catalog/QA/Governance agent specs to create Source Map and Master Index updates.
3. Keep GitHub as the runtime and Drive as the business knowledge layer.
