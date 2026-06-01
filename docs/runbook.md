# ARTSTUDIO Control Center Runbook

## 0. Current Legacy Structure Pass

For the current ARTSTUDIO Drive state, run `mainExecuteSafeActions()` before the general preparation pass. The Reorganization Plan already contains accepted rows for creating `01_INBOX` and `03_Object_Data` and for renaming legacy root folders into the new numbering.

This avoids creating empty target folders first and then renaming old populated folders into the same names.

Expected result:

- legacy folders are renamed into the approved structure;
- `01_INBOX` and `03_Object_Data` are created if missing;
- execution results are written back to Reorganization Plan.

## 1. Prepare Structure

Run `mainPrepareDriveStructure()` in Apps Script after the legacy structure pass.

Expected result:

- any still-missing canonical folders are created under ARTSTUDIO;
- `98_Project_Methodology` and `99_Setup_Archive` are created inside `00_CONTROL_CENTER`;
- Tool Run Log receives a preparation entry.

## 2. Audit

Run `mainAuditOnly()`.

Expected result:

- `Drive Audit Snapshot` is recreated;
- `Duplicate Report` is recreated;
- `Naming Issues` is recreated;
- new recommendations are appended to `ARTSTUDIO_Reorganization_Plan` without overwriting existing rows.

## 3. Review

Review rows in `ARTSTUDIO_Reorganization_Plan`.

Use these values:

- `Human decision = accepted` for actions approved by a person;
- `Human decision = rejected` for actions that must not run;
- `Human decision = needs discussion` for ambiguous rows;
- `Safe action = trash duplicate` only when the duplicate is obvious;
- `Safe action = no automated action` when the action should remain manual.

## 4. Execute Safe Actions

Run `mainExecuteSafeActions()` again after review if audit creates new executable rows.

The script executes rows when either:

- `Human decision = accepted`; or
- the row has an auto-safe action and risk is not high.

Supported execution actions:

- create folder;
- move file;
- move folder;
- rename file;
- rename folder;
- archive setup artifact;
- move methodology file;
- trash duplicate.

The script never performs permanent deletion and never changes permissions.

## 5. Validate

Run `mainValidateStageTwoReadiness()`.

Expected result:

- canonical folders exist;
- control files exist;
- GitHub policy is reflected in Drive rules;
- unresolved high-risk rows remain blocked;
- Tool Run Log has entries for execution, prepare, audit and validation.

## 6. GitHub Validation

Run the `Validate knowledge ops` workflow in GitHub Actions or let it run on push.

Expected result:

- `config/control-center.json` parses successfully;
- required repo files exist;
- Apps Script contains required entrypoints;
- deployment workflow is present.

## 7. Deployment

Apps Script deployment is manual through `Deploy Apps Script` workflow.

Required secrets:

- `CLASPRC_JSON` - clasp authorization file content;
- optional `SCRIPT_ID` if the script project is already bound.

Deployment should be run only after validation passes.
