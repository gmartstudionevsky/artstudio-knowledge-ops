# ARTSTUDIO Knowledge Ops

Technical automation repository for the ARTSTUDIO Base / Google Drive knowledge system.

## Purpose

Google Drive remains the business knowledge base.  
GitHub is the automation source of truth for scripts, configs, tests, workflows and Codex tasks.

## Core principle

Machine proposes, human approves, automation executes only safe approved actions.

## Main components

- `apps-script/control-center` — Google Apps Script code for Drive automation.
- `config` — canonical folder IDs, file names, statuses, naming rules.
- `docs` — architecture, runbooks and Codex handoff notes.
- `.github/workflows` — CI, deployment and safe automation workflows.
- `tests` — config and rule validation tests.

## Current stage

Stage 1: Create and seal `00_CONTROL_CENTER`.

Canonical Google Drive folders:

- ARTSTUDIO: `17dKXkxMd_iiBz5AFbKtt7YvuEzo-bfQK`
- 00_CONTROL_CENTER: `13riY7cN6DjiYg1k9ey19sdFgva8cP7dp`
