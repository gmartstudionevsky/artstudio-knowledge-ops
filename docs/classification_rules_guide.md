# Classification Rules Guide

## Safe Rule Workflow

1. Add or edit a small group of YAML rules.
2. Run `validate-rules`.
3. Run unit tests.
4. Run a metadata-only sample inventory.
5. Review unknowns, conflicts, zero-hit rules and slow rules.
6. Only then expand the next group of rules.

## Validation

```bash
python -m knowledge_ops.drive_inventory validate-rules \
  --config configs/drive_inventory.yml \
  --out-dir out/classification_engine_diagnostics
```

Validation checks:

- duplicate rule IDs;
- invalid regex;
- empty selectors;
- unknown target fields;
- unsafe DELETE actions;
- short or broad tokens;
- accidental disabling of Google Sheets skip;
- accidental enabling of Cloud AI or sensitive uploads.

## Rule Design

Prefer specific path/filename phrases over very broad single words. Broad tokens like `акт`, `фото`, `документ`, `КУ` can create false positives unless they are scoped by path or paired with stronger signals.

Use `target_fields` to set only fields the rule can reasonably support. The final V3 merge layer will calculate confidence, evidence, conflicts and review queues.

## Regression

Indexed mode should match full-scan mode on representative examples. If a future rule intentionally changes classification behavior, add a focused test explaining the change.
