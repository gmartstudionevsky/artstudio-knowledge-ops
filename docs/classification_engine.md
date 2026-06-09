# Classification Engine Diagnostics

## Purpose

The classification engine is optimized for safe rule growth. It keeps the current YAML rule format, but compiles rules once at startup and can run either in indexed mode or strict full-scan mode.

This layer does not read Google Sheets, does not enable OCR, does not call Cloud AI APIs, and does not write anything back to Google Drive.

## Engine Modes

- `indexed`: default mode. Token, extension and MIME selectors are indexed before the scan. Regex-only rules and fallback rules are still evaluated safely.
- `full_scan`: compatibility mode. Every item is checked against every rule in source order. Use it for debugging and equivalence tests.

Config:

```yaml
drive_inventory:
  classification_engine:
    use_rule_index: true
    strict_full_scan: false
    normalization_cache_size: 50000
    slow_rule_ms: 2.0
```

To force full scan, set `strict_full_scan: true` or `use_rule_index: false`.

## What Is Compiled

At config load time the engine prepares:

- normalized tokens;
- compiled regex patterns;
- normalized negative tokens;
- compiled negative regex patterns;
- extension sets;
- MIME prefix tuples;
- rule category, source, weight and target fields.

Invalid regex patterns are recorded in diagnostics and validation reports. A bad regex is disabled instead of crashing the full pipeline.

## Rule Validation

Run locally:

```bash
python -m knowledge_ops.drive_inventory validate-rules \
  --config configs/drive_inventory.yml \
  --out-dir out/classification_engine_diagnostics
```

Outputs:

- `rule_validation_report.md`
- `rule_validation_errors.csv`
- `rule_validation_warnings.csv`

Validation checks duplicate `rule_id`, invalid regex, empty selectors, non-numeric weights, unknown target fields, forbidden `DELETE` actions, duplicate selector/target signatures and risky short tokens.

## Performance Outputs

Every inventory report now adds:

- `classification_performance.json`
- `classification_performance.md`
- `rule_performance.csv`
- `zero_hit_rules.csv`
- `slow_rules.csv`
- `suspicious_rules.csv`
- `classification_quality_summary.csv`
- `classification_quality_summary.md`

The Excel workbook also includes `Rule Performance` and `Quality Summary` sheets.

## Reading Rule Performance

Use `rule_performance.csv` to find:

- rules with many matches and high confidence contribution;
- zero-hit rules that may be obsolete or too narrow;
- slow rules that need regex/token cleanup;
- regex errors;
- sanitized example paths for quick review.

`example_paths` are intentionally shortened and must not include document content.

## Quality Metrics

After every rule update, compare:

- unknown object count;
- unknown department count;
- unknown document type count;
- sensitivity known/unknown count;
- `NEEDS_REVIEW` count;
- conflict count;
- `classification_status` distribution;
- `combined_confidence` distribution;
- average classification time;
- zero-hit and slow-rule counts.

The main goal is to reduce unknowns without increasing conflicts or materially slowing classification.

## Regression Guardrail

Tests compare indexed mode against full-scan mode on representative ARTSTUDIO/RBI PM examples. If a future optimization changes meaning, the diff should be explicit and covered by a test.

Run:

```bash
python -m unittest tests.test_drive_inventory
```

For CI-only validation without a Drive scan, use GitHub Actions -> `Classification Engine Diagnostics` -> `Run workflow`.

## Adding New Rules Safely

1. Add or edit YAML rules.
2. Run `validate-rules`.
3. Run `python -m unittest discover tests`.
4. Run a small metadata-only inventory.
5. Review `rule_performance.csv`, `zero_hit_rules.csv`, `slow_rules.csv`, `suspicious_rules.csv` and `classification_quality_summary.csv`.
6. Compare unknown, conflict and review rates against the previous run.

Do not use this stage to perform Drive writes, apply migrations, enable OCR or call Cloud AI APIs.
