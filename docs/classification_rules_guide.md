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

## V3.1 Real Drive Pattern Rules

V3.1 rules are based on real names and paths from the first metadata map, but they must not turn accidental folder names into final business context. Add narrowly scoped rules for actual Drive patterns, then protect them with regression tests.

Do:

- prefer exact phrases from filenames and stable folder names;
- use `regex_patterns` for contextual abbreviations;
- add `negative_tokens` or `negative_regex_patterns` when a token is likely to appear inside unrelated words;
- add fixture examples in `tests/fixtures/classification_v3_real_patterns.yml`;
- run `validate-rules` and unit tests after every rule batch.

Do not:

- use `АД`, `РД`, `ДД`, `ТО`, `КУ`, `АН`, `АМ` or `КП` as free substring tokens;
- classify files inside `/ARTSTUDIO/04_Standards_SOP`, `/ARTSTUDIO/06_OTA`, `/ARTSTUDIO/08_Legal_Files`, `/ARTSTUDIO/09_Owner_Investor`, `/ARTSTUDIO/02_Brand_Context` or `/ARTSTUDIO/03_Object_Data` from that folder name alone;
- add `DELETE` as an action recommendation;
- make Cloud AI or OCR calls from rule validation.

## Contextual Short Abbreviation Rules

Short abbreviations need business context:

- `АД` only with agency-contract context such as `Агентские`, `АПП к АД` or `Приложение к АД`.
- `РД` only with `Равный доход`, `Аренда РД`, `Агентский РД` or `АМ Аренда РД`.
- `ДД` only with `Динамический доход` or agency-DD context.
- `ТО` only with `Договор ТО`, `Договоры на ТО`, `Техобслуживание` or `техническое обслуживание`.
- `КУ` only with `КУ/Квитанции`, `Начисления КУ`, `Реестр КУ`, `Квитанции КУ` or `коммунальные услуги`.
- `КП` only with `КП и счета`, `КП + счета`, `КП по ...` or `коммерческое предложение`.

Approved short domain codes such as `ДКП`, `ДДУ`, `АПП`, `УПД`, `ППР`, `РКО`, `БИК`, `ИНН`, `SMM`, `OTA` and `NPS` are allowed by validation because they are stable document or department markers. They still need tests when used in a new rule family.

## Priority Overrides

Some signals intentionally override weaker metadata:

- system trash files such as `Thumbs.db`, `.DS_Store`, `desktop.ini`, `~$*`, `.tmp`, `.lnk` and `.wbk` become `CLASSIFIED_SYSTEM_TRASH`;
- signature/stamp assets become `signature_seal_sensitive`, `DO_NOT_TOUCH` and `legal_hold_review`;
- `/Отдел продаж/Договоры/` stays in Sales/corporate context unless owner context is explicit;
- `/Front Office/Документы по номерам в управлении/` is routed to owner-contract review;
- `/Housekeeping/Отчеты/YYYY/...` is a housekeeping daily report even when the filename is unclear;
- `ChatExport` thumbnails and metadata stay in chat-export review and are not normal marketing photos.

## How To Read False-Positive Guards

False-positive guards are visible in three places:

- `negative_tokens` and `negative_regex_patterns` in YAML rules prevent known bad matches;
- `classification_reason` explains when `/ARTSTUDIO/` path context was ignored;
- `rule_validation_warnings.csv` highlights broad or short tokens that need review unless they are in the approved short-token allowlist.

When a rule is intentionally broad, add a negative fixture. Examples: `НАДЕЖДА` must not trigger `АД`, `КПП` must not trigger `КП`, and arbitrary words containing `КУ` must not trigger utility receipts.

## Regression

Indexed mode should match full-scan mode on representative examples. If a future rule intentionally changes classification behavior, add a focused test explaining the change.
