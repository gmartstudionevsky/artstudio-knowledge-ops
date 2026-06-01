# ARTSTUDIO Knowledge Ops Architecture

## System Roles

Google Drive is the business knowledge base. It stores source materials, working documents, indexes, decision logs and operational context.

GitHub is the automation source of truth. It stores Apps Script code, configuration, workflow definitions, runbooks and agent specifications.

The control center is `00_CONTROL_CENTER` inside the ARTSTUDIO Drive folder. It is not the whole knowledge base; it is the governance layer that keeps the knowledge base navigable, auditable and automatable.

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
7. Apps Script executes safe approved actions and writes execution logs.

## Safe Actions

Safe actions are actions that are reversible or low-risk when they are scoped to an explicit object ID and logged:

- create missing canonical folder;
- move file or folder into the approved structure;
- rename file or folder to an approved target name;
- archive setup or methodology artifacts;
- trash obvious duplicates.

Trash means `setTrashed(true)` in Google Drive. Permanent deletion is not allowed.

## Obvious Duplicate Rule

An object can be trashed automatically only when the duplicate check finds a canonical object in the correct folder, the name and MIME type match, no unique content is detected, and the object is not a folder with unique children. Otherwise the action becomes `human review required`.

## GitHub Workflows

- `validate.yml` checks required files, validates JSON and performs basic Apps Script sanity checks.
- `deploy-apps-script.yml` is manual and requires repository secrets for clasp-based deployment.

## Audit Trail

Every meaningful run must update Tool Run Log. Every structural or policy decision must be recorded in Decision Log. Automation recommendations are written to Reorganization Plan before execution.
