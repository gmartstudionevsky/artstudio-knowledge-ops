# Runbook

## Bootstrap

Use `bootstrap_control_center.gs` only for initial creation.

## Sealing audit

Use `apps-script/control-center/control_center_sealing.gs` for Stage 1 sealing.
The first production version is audit-only. It must not delete files, change
permissions, move objects, or rename objects.

Before running, confirm the config defaults are still safe:

- `dryRun: true`
- `executeAcceptedActions: false`
- `allowDelete: false`

Run:

```javascript
mainAuditOnly()
```

Expected outputs in `ARTSTUDIO_Reorganization_Plan`:

- `Main` receives new recommendation rows only when `Object ID + Detection rule`
  is not already present.
- Existing `Human decision` values in `Main` are preserved.
- `Drive Audit Snapshot` is refreshed with the current Drive scan.
- `Duplicate Report` is refreshed with canonical control-file duplicates outside
  `00_CONTROL_CENTER`.
- `Naming Issues` is refreshed and carries forward existing human decisions when
  the same object/rule is still present.
- `Stage 1 Sealing Validation` is refreshed with closure checks.
- `ARTSTUDIO_Tool_Run_Log` receives a completed audit-only run entry when the log
  spreadsheet is reachable.

Review the recommendations manually. Machine recommendations are not final
decisions.

## Execute approved actions

Execution is intentionally blocked in the first production audit-only release.
Do not run an execution flow until a separate approved implementation exists.

Future execution may run only after reviewing `ARTSTUDIO_Reorganization_Plan` and
setting specific rows to `Human decision = accepted`:

```javascript
mainExecuteAcceptedActions()
```

## Validate closure

Run validation after audit, and again after any future accepted execution flow:

```javascript
mainValidateStageOneClosure()
```
