# ARTSTUDIO Knowledge Ops Architecture

## System Roles

Google Drive is the business knowledge base. It stores source materials, working documents, indexes, decision logs and operational context.

GitHub is both the automation source of truth and the native execution environment. It stores configuration, workflow definitions, runbooks, agent specifications and the Python runtime that operates against Google Drive and Google Sheets through a service account.

Apps Script is legacy only. It can remain as historical reference, but the controlled execution path is GitHub Actions.

The control center is `00_CONTROL_CENTER` inside the ARTSTUDIO Drive folder. It is not the whole knowledge base; it is the governance layer that keeps the knowledge base navigable, auditable and automatable.

## Native Execution Model

The primary runtime is:

- GitHub Actions workflow: `.github/workflows/drive-ops.yml`
- Python entrypoint: `knowledge_ops.native_drive_ops`
- Google auth: `GOOGLE_SERVICE_ACCOUNT_JSON` repository secret
- Business state: Google Drive and control-center Google Sheets

The workflow can run three operations:

- `validate-readiness` - check folder/control-file readiness and write a validation sheet.
- `execute-safe-actions` - execute accepted or auto-safe rows from `ARTSTUDIO_Reorganization_Plan`.
- `prepare-structure` - create missing canonical folders after legacy rename actions are handled.

## Canonical Drive Structure

- `00_CONTROL_CENTER` - indexes, logs, rules, project methodology and automation control.
- `01_INBOX` - single intake point for new or unclassified materials.
- `02_Brand_Context` - brand, tone, visual rules and communication context.
- `03_Object_Data` - factual object-level data and property materials.
- `04_Standards_SOP` - standards, SOPs, scripts and procedures.
- `05_Official_Sites` - official site content and web snapshots.
- `06_OTA` - OTA profiles, descriptions and platform materials.
- `07_Reviews` - guest reviews and feedback analysis.
- `08_Legal_Files` - contracts, templates and legal material.
- `09_Owner_Investor` - owner, investor and yield materials.
- `10_Competitors_Market` - competitors, market context and benchmarks.

Inside `00_CONTROL_CENTER`:

- `98_Project_Methodology` - Stage 0 methodology and project framing artifacts.
- `99_Setup_Archive` - bootstrap, setup and historical automation artifacts.

## Automation Flow

1. New materials enter `01_INBOX`.
2. Intake Agent creates draft Source Map and Master Index rows.
3. Catalog Agent proposes a target folder and naming changes.
4. QA Agent checks duplicates, contradictions and unique content risk.
5. Governance Agent checks owners, statuses, decisions and open questions.
6. Human approval is required for high-risk or meaning-changing actions.
7. GitHub Actions executes safe approved actions and writes execution logs.

## Safe Actions

Safe actions are reversible or low-risk when scoped to an explicit object ID and logged:

- create missing canonical folder;
- move file or folder into the approved structure;
- rename file or folder to an approved target name;
- archive setup or methodology artifacts;
- trash obvious duplicates.

Trash means Google Drive `files.update(trashed=true)`. Permanent deletion is not allowed.

## Obvious Duplicate Rule

An object can be trashed automatically only when the duplicate check finds a canonical object in the correct folder, the name and MIME type match, no unique content is detected, and the object is not a folder with unique children. Otherwise the action becomes `human review required`.

## Secrets And Access

Required:

- `GOOGLE_SERVICE_ACCOUNT_JSON`

Optional:

- `GOOGLE_DELEGATED_USER`
- `ARTSTUDIO_FOLDER_ID`
- `CONTROL_CENTER_FOLDER_ID`
- `OPENAI_API_KEY`
- `SLACK_WEBHOOK_URL`

The service account must be shared with the ARTSTUDIO root folder and `00_CONTROL_CENTER` as Editor.

## Audit Trail

Every meaningful run must update Tool Run Log. Every structural or policy decision must be recorded in Decision Log. Automation recommendations are written to Reorganization Plan before execution.
