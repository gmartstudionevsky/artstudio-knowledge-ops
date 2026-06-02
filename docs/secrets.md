# GitHub Secrets And Google Access

This repository uses GitHub Actions as the primary execution runtime. Google Apps Script is legacy only.

## Required Secret

### `GOOGLE_SERVICE_ACCOUNT_JSON`

Full JSON key for a Google Cloud service account.

The JSON must include at least:

- `client_email`
- `private_key`
- `project_id`

The service account must be shared into the ARTSTUDIO Drive workspace with enough access to:

- read the ARTSTUDIO root folder;
- read and create folders under the ARTSTUDIO root folder;
- read and update files/folders that can be renamed or moved;
- move delete-candidate objects into `00_CONTROL_CENTER/99_Setup_Archive/00_PENDING_TRASH`;
- read and update control-center spreadsheets;
- read Google Docs when document checks are added later.

Minimum practical Drive sharing setup:

1. Share the ARTSTUDIO root folder with the service account email as Editor.
2. Share `00_CONTROL_CENTER` and all control-center spreadsheets with the same service account as Editor.
3. Ensure inherited permissions are not blocked on nested folders that automation must move or rename.
4. Share project files outside ARTSTUDIO with the service account before expecting workflow discovery or movement.

Editor access may still be insufficient for Drive trash on objects owned by another account. The strict runtime therefore moves approved delete candidates into `00_PENDING_TRASH` and logs them instead of relying on owner-level trash permission.

## Optional Secrets

Optional secrets may be omitted. Empty optional values are ignored by the runtime, so the workflow falls back to `config/control-center.json`.

### `GOOGLE_DELEGATED_USER`

Use only if Google Workspace domain-wide delegation is configured and the service account must impersonate a real workspace user. This is useful when Drive permissions are easier to manage through one delegated user.

### `ARTSTUDIO_FOLDER_ID`

Overrides the folder ID stored in `config/control-center.json`. Use only if moving the system to another Drive folder or testing against a sandbox.

### `CONTROL_CENTER_FOLDER_ID`

Overrides the control-center folder ID stored in `config/control-center.json`. Use only for sandbox or migration runs.

### `OPENAI_API_KEY`

Reserved for later semantic agent steps: classification, summarization, contradiction detection and drafting. It is not required for the current Drive operations workflow.

### `SLACK_WEBHOOK_URL`

Reserved for future notifications after workflow runs. It is not required for the current Drive operations workflow.

## GitHub Built-In Token

`GITHUB_TOKEN` is provided by GitHub Actions automatically. It does not need to be created as a secret for the current workflow. Current workflow permissions are `contents: read`.

## Recommended First Run

1. Add `GOOGLE_SERVICE_ACCOUNT_JSON`.
2. Share ARTSTUDIO Drive folders, control spreadsheets and outside project files with the service account email.
3. Run `Validate knowledge ops`.
4. Run `GitHub-native Drive Ops` with:
   - `command = validate-readiness`
   - `dry_run = true`
5. Run `GitHub-native Drive Ops` with:
   - `command = complete-prep`
   - `dry_run = false`
6. Review `ARTSTUDIO_Reorganization_Plan`, especially `Pending Trash Queue`, `Folder Duplicate Audit` and remaining manual rows.
7. Run `validate-readiness` with `dry_run = false`.

## Security Rule

Never commit service account JSON to the repository. Store it only in GitHub Secrets or in the local environment variable `GOOGLE_APPLICATION_CREDENTIALS` for local testing.
