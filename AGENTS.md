# AGENTS.md

You are working on ARTSTUDIO Knowledge Ops automation.

## Business context

ARTSTUDIO Base is a context-first, digitally enabled, human-governed knowledge system for RBI PM / ARTSTUDIO.  
Google Drive is the business workspace. GitHub is the technical automation control plane.

The system is not purely machine-first. Human participants provide missing internal context, upload files, confirm operational reality, approve structures, make governance decisions and accept final results. Automation handles analysis, classification, editing, scripting, comparison, logging and repeatable processing.

## Core rules

- Never delete Google Drive files by default.
- Never change permissions without explicit human approval.
- Never overwrite human decisions.
- All scripts must support audit-only / dry-run mode.
- Execution scripts must act only on rows where `Human decision = accepted`.
- High-risk actions must remain blocked unless explicitly approved.
- Machine recommendations are not final decisions.
- Final decisions must be logged in `ARTSTUDIO_Decision_Log`.
- Tool activity must be logged in `ARTSTUDIO_Tool_Run_Log`.
- Missing context must be logged in `ARTSTUDIO_Context_Request_Log`.
- Reorganization actions must be written to `ARTSTUDIO_Reorganization_Plan`.
- Prefer archive/move over deletion.
- Keep Google Drive as the business source of truth for documents and tables.
- Keep GitHub as the source of truth for automation code, configs and workflows.

## Google Drive canonical folders

- ARTSTUDIO folder ID: `17dKXkxMd_iiBz5AFbKtt7YvuEzo-bfQK`
- 00_CONTROL_CENTER folder ID: `13riY7cN6DjiYg1k9ey19sdFgva8cP7dp`

## Canonical control center files

- ARTSTUDIO_Master_Index
- ARTSTUDIO_Source_Map
- ARTSTUDIO_Decision_Log
- ARTSTUDIO_Open_Questions
- ARTSTUDIO_Project_Roadmap
- ARTSTUDIO_Reorganization_Plan
- ARTSTUDIO_Glossary
- ARTSTUDIO_Context_Request_Log
- ARTSTUDIO_Tool_Run_Log
- ARTSTUDIO_Codex_Handoff_Log
- ARTSTUDIO_Drive_Rules

## Development expectations

- Update docs when changing behavior.
- Update tests when changing rules.
- Keep config separate from code.
- Do not hardcode secrets.
- Use GitHub Secrets for credentials.
- Keep workflows safe by default.
- Make PR summaries operationally clear: what changes, why, risk level, how to test, how to roll back.

## Preferred implementation model

1. Audit-only scripts collect state and write reports.
2. Reorganization plan rows are generated with recommendations.
3. Human approves specific rows in Google Sheets.
4. Execution script performs only accepted rows.
5. Validation script checks closure criteria.
6. Logs are updated.
