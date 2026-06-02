# ARTSTUDIO Knowledge Ops

Technical automation repository for the ARTSTUDIO Base / Google Drive knowledge system.

## Purpose

Google Drive remains the business knowledge base.
GitHub is the automation source of truth and execution runtime for configs, workflows, runbooks, agent specs and Drive operations.

## Runtime

Primary execution is GitHub Actions + Google service account.

Apps Script is legacy only. It may remain in the repository for historical reference, but it is no longer the primary automation path.

## Core Principle

Machine proposes, human approves where risk is meaningful, and GitHub-native automation executes safe actions. The approved safe-action set includes creating folders, moving files or folders into the agreed structure, renaming by explicit target name, archiving setup and methodology artifacts, and trashing obvious duplicates. Permanent deletion is not allowed.

## Main Components

- `knowledge_ops/native_drive_ops.py` - GitHub-native Drive/Sheets execution CLI.
- `config/control-center.json` - canonical folder IDs, runtime, statuses, naming rules and automation policy.
- `config/agents.yml` - managed agent roles and approval boundaries.
- `docs` - architecture, runbook, secrets and operational handoff notes.
- `.github/workflows/drive-ops.yml` - manual GitHub-native Drive operations workflow.
- `.github/workflows/validate.yml` - repository and runtime validation workflow.
- `apps-script/control-center` - legacy Apps Script reference, not the primary runtime.

## Current Stage

Stage 2: prepare GitHub-native execution + agents + Drive intake, then start loading existing materials.

Canonical Google Drive folders:

- ARTSTUDIO: `17dKXkxMd_iiBz5AFbKtt7YvuEzo-bfQK`
- 00_CONTROL_CENTER: `13riY7cN6DjiYg1k9ey19sdFgva8cP7dp`
- 01_INBOX: created/validated by GitHub-native Drive Ops

## Required Secret

Add `GOOGLE_SERVICE_ACCOUNT_JSON` in GitHub repository secrets. Share the ARTSTUDIO root folder and `00_CONTROL_CENTER` with the service account email as Editor.

See `docs/secrets.md` for optional secrets and access setup.

## Operating Model

1. New material enters `01_INBOX`.
2. Intake and Catalog agents classify it and write recommendations.
3. Governance and QA agents check owners, statuses, duplicates and risks.
4. Human decision is required for high-risk or meaning-changing updates.
5. GitHub Actions executes approved or auto-safe rows and logs every result.

## First Run

1. Run `Validate knowledge ops`.
2. Run `GitHub-native Drive Ops` with `command = validate-readiness`, `dry_run = true`.
3. Run `GitHub-native Drive Ops` with `command = execute-safe-actions`, `dry_run = true`.
4. If clean, run `execute-safe-actions` with `dry_run = false`.
5. Run `prepare-structure` with `dry_run = false`.
6. Run `validate-readiness` with `dry_run = false`.
