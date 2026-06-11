# ARTSTUDIO Knowledge Ops

Репозиторий для read-only инвентаризации корпоративного Google Drive ARTSTUDIO / RBI PM.

Текущий этап проекта — собрать фактическую карту Drive: файлы, папки, Google Sheets как пропущенные объекты, дубли, первичную классификацию, чувствительные зоны, ограниченный анализ содержимого и оценку пригодности будущего Cloud AI-анализа.

Структурирование Drive, создание папок, переносы, переименования, карантин дублей и любые apply-операции намеренно убраны из репозитория. Новая целевая структура будет утверждаться позже на основании результатов инвентаризации.

## Принципы

- Только read-only аудит.
- Никаких изменений в Google Drive.
- Native Google Sheets не читаются, не экспортируются и не хешируются.
- Полный текст документов и чувствительные snippets не сохраняются по умолчанию.
- Cloud AI API не вызываются в estimate mode.
- Все результаты пишутся только в `out/`, который не попадает в git.

## Основные компоненты

- `knowledge_ops/drive_inventory` — инвентаризация Drive, классификация, дубли, content inspection, отчеты.
- `knowledge_ops/ai_analysis` — estimate-only подготовка будущего Cloud AI-анализа и расчет примерной стоимости.
- `configs/drive_inventory.yml` — параметры инвентаризации.
- `configs/drive_classification_taxonomy.yml` — Taxonomy V2: статусы, объекты, подразделения, семейства документов и cleanup-категории.
- `configs/drive_path_rules.yml`, `configs/drive_filename_rules.yml`, `configs/drive_extension_rules.yml`, `configs/drive_sensitivity_rules.yml`, `configs/drive_media_rules.yml`, `configs/drive_cleanup_rules.yml` — первичная metadata-only классификация по пути, имени, формату, чувствительности, медиа и cleanup-сигналам.
- `configs/drive_content_rules.yml` — правила content inspection.
- `configs/corpus_sieve_rules.yml` — Stage 1 rules for exact duplicate suppression, system trash exclusion, archive holds and canonical corpus dry-run.
- `configs/ai_analysis_pricing.yml` — оценочные цены Cloud AI.
- `configs/ai_analysis_routing.yml` — сценарии, маршрутизация и budget guards.
- `.github/workflows/drive-inventory.yml` — последовательный workflow инвентаризации.
- `.github/workflows/ai-analysis-estimate.yml` — отдельный estimate-only workflow для AI readiness.

## Последовательный workflow инвентаризации

### Workflow Run Modes

Use `classification_run_mode` in `Actions` -> `Drive Inventory Pipeline` -> `Run workflow`:

- `metadata_registry` - builds only the complete Drive metadata registry. It uses `--mode inventory`, does not apply V3/V3.1 classification, does not read file content, and produces `drive-inventory-01-metadata`.
- `metadata_classification_only` - recommended first run after V3/V3.1 rule changes. It applies path/filename/extension/sensitivity/media/cleanup/lifecycle/source-origin/duplicate rules with `--mode metadata-classification`, respects the workflow `max_files` input, keeps `--enable-content-inspection false`, `--enable-ocr false`, no Cloud AI, and produces `drive-inventory-metadata-classification`. Set `max_files=0` for a full scan; keep `metadata_max_runtime_minutes` enabled if you want partial artifacts instead of a runner cancellation.
- `corpus_sieve` - runs `metadata_classification_only` first, then builds Stage 1 canonical corpus artifacts from `classification_v3_inventory.csv` without touching Drive. It produces `drive-inventory-corpus-sieve`.
- `bounded_content_classification` - runs the existing bounded content inspection stage with limits. Use it only after reviewing metadata classification results.
- `full_with_content` - runs the final read-only inventory with content inspection and optional estimate-only AI readiness. Use it after `metadata_classification_only` looks sane.

`metadata_only_registry=true` remains as a legacy override for a pure registry run.

Workflow `Drive Inventory Pipeline` выполняет этапы:

1. `01 metadata map` — быстрый metadata-only реестр без скачивания содержимого.
2. `02 metadata classification only` — metadata-классификация без content/OCR/Cloud AI.
3. `03 corpus sieve dry-run` — Stage 1 отсев exact-дублей, system trash, installers, archive-hold и review queue по готовому CSV.
4. `02 content classification` — ограниченный content inspection и классификация по правилам.
5. `03 final inventory reports` — итоговые отчеты, дубли, sensitivity review, Excel.
6. `04 AI readiness estimate` — estimate-only расчет пригодности и стоимости будущего Cloud AI-анализа.

См. [docs/inventory_workflow.md](docs/inventory_workflow.md).

В GitHub он находится так: `Actions` -> `Drive Inventory Pipeline` -> `Run workflow`.
Файл workflow: `.github/workflows/drive-inventory.yml`.
Рабочий конфиг: `configs/drive_inventory.yml`.

При ручном запуске должны быть видны параметры:

- `scope`
- `root_folder_id`
- `max_files`
- `metadata_max_runtime_minutes`
- `content_inspection_max_files`
- `content_char_limit`
- `content_page_limit`
- `max_download_size_mb`
- `classification_run_mode`
- `metadata_only_registry`
- `enable_ocr`
- `generate_ai_estimate`

Для запуска из GitHub Actions нужен repository secret `GOOGLE_SERVICE_ACCOUNT_JSON`.
Опционально можно добавить `GOOGLE_DELEGATED_USER`, если используется domain-wide delegation.

## Локальный запуск инвентаризации

```bash
python -m knowledge_ops.drive_inventory \
  --scope all-accessible-drive \
  --config configs/drive_inventory.yml \
  --out-dir out/drive_inventory \
  --mode full \
  --skip-google-sheets true \
  --dry-run true \
  --enable-content-inspection true \
  --content-inspection-max-files 100 \
  --store-content-preview false \
  --store-sensitive-snippets false
```

## GitHub Actions: полный прогон

1. Откройте GitHub repository -> `Actions` -> `Drive Inventory Pipeline`.
2. Нажмите `Run workflow`.
3. Для первого безопасного полного реестра выберите `metadata_only_registry=true`. Workflow пройдёт по всем доступным service account объектам, принудительно использует `max_files=0`, не скачивает содержимое и отдаст artifact `drive-inventory-01-metadata`.
4. Для полноценной предварительной классификации выберите `metadata_only_registry=false`, `max_files=0`, `content_inspection_max_files=0`, `enable_ocr=true`, `generate_ai_estimate=true`. Этот режим скачивает поддерживаемые файлы в пределах лимитов, пытается извлечь текст из документов/PDF и, где возможно, делает локальный OCR изображений и сканов.
5. После завершения скачайте artifacts. Основные файлы для разбора: `all_objects.csv`, `inventory.csv`, `content_inspection.csv`, `classification_review.csv`, `sensitivity_review.csv`, `access_coverage.csv`, `object_classification_summary.csv`, `department_classification_summary.csv`, `document_type_summary.csv`, `unknown_after_v2.csv`, `cleanup_candidates.csv`, `rule_match_summary.csv`, `inventory.xlsx`, `audit_report.md`.

`all_objects.csv` — полный реестр всего увиденного, включая Google Sheets как metadata-only объекты. `inventory.csv` — рабочий реестр файлов для классификации, без содержимого Google Sheets.

Для сравнения качества Taxonomy V2 с первым полным реестром смотрите долю `UNKNOWN`, количество `CONFLICT_METADATA`, распределение `classification_status`, топ правил в `rule_match_summary.csv`, кандидатов в `cleanup_candidates.csv` и остаток ручной проверки в `unknown_after_v2.csv`.

## Локальный запуск AI estimate

```bash
python -m knowledge_ops.ai_analysis \
  --inventory out/drive_inventory/inventory.csv \
  --content-inspection out/drive_inventory/content_inspection.csv \
  --out-dir out/ai_analysis_estimate \
  --mode estimate \
  --pricing-config configs/ai_analysis_pricing.yml \
  --routing-config configs/ai_analysis_routing.yml \
  --dry-run true
```

## Classification Engine Diagnostics / Rule Validation

Для проверки правил без Drive-аудита:

```bash
python -m knowledge_ops.drive_inventory validate-rules \
  --config configs/drive_inventory.yml \
  --out-dir out/classification_engine_diagnostics
```

После inventory-прогона смотрите `classification_performance.json`, `classification_performance.md`, `rule_performance.csv`, `zero_hit_rules.csv`, `slow_rules.csv`, `suspicious_rules.csv` и `classification_quality_summary.csv`.

Отдельный GitHub Actions workflow: `Classification Engine Diagnostics`. Он запускается вручную, не требует Google Drive secrets и не делает Cloud AI calls.

## Classification V3 / Deep Classification Layer

V3.1 adds real Drive pattern hardening: contextual short abbreviations, priority overrides and protection from false path context in `/ARTSTUDIO/`. The auto-structured `/ARTSTUDIO/` subfolders are treated as staging markers, not as reliable business taxonomy; files there are classified by filename, extension, MIME, metadata, content inspection and later OCR/content evidence.

V3 добавляет расширенную taxonomy, regex entity extraction, confidence/evidence fields, OCR/cloud candidates, human review queues и отдельные `classification_v3_*` отчеты. OCR и Cloud AI остаются выключенными по умолчанию; текущий слой только формирует кандидатов и approval queues.

Основные документы: [docs/classification_v3.md](docs/classification_v3.md), [docs/ocr_pipeline.md](docs/ocr_pipeline.md), [docs/human_review_queues.md](docs/human_review_queues.md), [docs/classification_rules_guide.md](docs/classification_rules_guide.md).

## Credentials

Для реального Drive-листинга нужен один из вариантов:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_APPLICATION_CREDENTIALS`

Опционально:

- `GOOGLE_DELEGATED_USER`

Service account должен иметь доступ на чтение к тем Drive-зонам, которые нужно инвентаризировать. Editor-доступ не требуется для текущего этапа.

В GitHub Actions используется только `GOOGLE_SERVICE_ACCOUNT_JSON`; локальный вариант `GOOGLE_APPLICATION_CREDENTIALS` оставлен для запуска с машины разработчика.

## Документация

- [docs/drive_inventory.md](docs/drive_inventory.md) — инвентаризация и отчеты.
- [docs/classification_engine.md](docs/classification_engine.md) — diagnostics, indexed/full-scan режимы и validation правил.
- [docs/classification_v3.md](docs/classification_v3.md) — Classification V3, review queues и V3 outputs.
- [docs/ocr_pipeline.md](docs/ocr_pipeline.md) — OCR candidate orchestration и guards.
- [docs/human_review_queues.md](docs/human_review_queues.md) — очереди ручной проверки.
- [docs/classification_rules_guide.md](docs/classification_rules_guide.md) — безопасное добавление правил.
- [docs/inventory_workflow.md](docs/inventory_workflow.md) — этапы workflow и рекомендуемый темп прогонов.
- [docs/ai_analysis_preparation.md](docs/ai_analysis_preparation.md) — подготовка Cloud AI-анализа и estimate.
