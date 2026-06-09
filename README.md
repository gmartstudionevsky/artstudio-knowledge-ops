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
- `configs/drive_content_rules.yml` — правила content inspection.
- `configs/ai_analysis_pricing.yml` — оценочные цены Cloud AI.
- `configs/ai_analysis_routing.yml` — сценарии, маршрутизация и budget guards.
- `.github/workflows/drive-inventory.yml` — последовательный workflow инвентаризации.
- `.github/workflows/ai-analysis-estimate.yml` — отдельный estimate-only workflow для AI readiness.

## Последовательный workflow инвентаризации

Workflow `Drive Inventory Pipeline` выполняет этапы:

1. `01 metadata map` — быстрый metadata-only реестр без скачивания содержимого.
2. `02 content classification` — ограниченный content inspection и классификация по правилам.
3. `03 final inventory reports` — итоговые отчеты, дубли, sensitivity review, Excel.
4. `04 AI readiness estimate` — estimate-only расчет пригодности и стоимости будущего Cloud AI-анализа.

См. [docs/inventory_workflow.md](docs/inventory_workflow.md).

В GitHub он находится так: `Actions` -> `Drive Inventory Pipeline` -> `Run workflow`.
Файл workflow: `.github/workflows/drive-inventory.yml`.
Рабочий конфиг: `configs/drive_inventory.yml`.

При ручном запуске должны быть видны параметры:

- `scope`
- `root_folder_id`
- `max_files`
- `content_inspection_max_files`
- `content_char_limit`
- `content_page_limit`
- `max_download_size_mb`
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
5. После завершения скачайте artifacts. Основные файлы для разбора: `all_objects.csv`, `inventory.csv`, `content_inspection.csv`, `classification_review.csv`, `sensitivity_review.csv`, `access_coverage.csv`, `inventory.xlsx`, `audit_report.md`.

`all_objects.csv` — полный реестр всего увиденного, включая Google Sheets как metadata-only объекты. `inventory.csv` — рабочий реестр файлов для классификации, без содержимого Google Sheets.

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
- [docs/inventory_workflow.md](docs/inventory_workflow.md) — этапы workflow и рекомендуемый темп прогонов.
- [docs/ai_analysis_preparation.md](docs/ai_analysis_preparation.md) — подготовка Cloud AI-анализа и estimate.
