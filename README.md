# ARTSTUDIO Knowledge Ops

Technical automation repository for the ARTSTUDIO Base / Google Drive knowledge system.

## Purpose

Google Drive remains the business knowledge base.
GitHub is the automation source of truth for scripts, configs, tests, workflows, runbooks and Codex handoff tasks.

## Core Principle

Machine proposes, human approves, automation executes safe actions. The approved safe-action set includes creating folders, moving files or folders into the agreed structure, renaming by explicit target name, archiving setup and methodology artifacts, and trashing obvious duplicates. Permanent deletion is not allowed.

## Main Components

- `apps-script/control-center` - Google Apps Script code for Drive automation.
- `config` - canonical folder IDs, file names, statuses, naming rules and agent definitions.
- `docs` - architecture, runbooks and operational handoff notes.
- `.github/workflows` - validation and deployment workflows.
- `tests` - future config and rule validation tests.

## Current Stage

Stage 2: prepare GitHub + Workflows + Agents + Drive intake, then start loading existing materials.

Canonical Google Drive folders:

- ARTSTUDIO: `17dKXkxMd_iiBz5AFbKtt7YvuEzo-bfQK`
- 00_CONTROL_CENTER: `13riY7cN6DjiYg1k9ey19sdFgva8cP7dp`
- 01_INBOX: to be created by Apps Script or Drive UI and then recorded in `config/control-center.json`

## Operating Model

1. New material enters `01_INBOX`.
2. Intake and Catalog agents classify it and write recommendations.
3. Governance and QA agents check owners, statuses, duplicates and risks.
4. Human decision is required for high-risk or meaning-changing updates.
5. Safe automation executes approved or auto-safe rows and logs every result.
