# Drive Inventory / первый этап инвентаризации Google Drive

## Назначение

`knowledge_ops.drive_inventory` - отдельный read-only контур для первого этапа аудита Google Drive. Он описывает доступные service account папки и файлы, находит дубли и кандидатов на разбор, формирует управленческие отчёты и черновую таблицу решений для следующего этапа.

Инструмент не проектирует финальную структуру Drive и не выполняет миграцию. Его задача - дать полную и объяснимую картину текущего состояния.

## Что инвентаризируется

- Все доступные service account объекты Drive при `--scope all-accessible-drive`.
- Дерево от конкретной папки при `--scope root` или `--scope folder --root-folder-id ...`.
- Папки, обычные файлы, Google Docs, Google Slides и прочие Google Workspace native объекты.
- Metadata: ID, имя, путь, MIME type, размер, checksum, даты, владельцы, parents, Drive ID, признаки shared/trashed/starred, краткий permissions summary.

## Почему Google Sheets пропускаются

Google Sheets на первом этапе фиксируются только в `skipped_google_sheets.csv` и листе `Skipped Google Sheets`. Их содержимое не читается, не экспортируется, не хешируется и не классифицируется по внутренним данным. Это сделано намеренно: таблицы часто содержат персональные, финансовые и операционные данные, а текущий этап должен быть безопасным обзором.

При этом Google Sheets остаются в `all_objects.csv` как metadata-only объекты, чтобы полный состав видимого Drive не терялся в downstream-аналитике.

## Metadata Classification Taxonomy V2

Первичная классификация теперь работает как отдельный metadata-only слой до любого AI-анализа. Он использует путь, имя файла, расширение, MIME type и служебные признаки, чтобы снизить долю `UNKNOWN` после полного реестра Drive.

Движок поддерживает indexed mode и strict full-scan mode. Indexed mode ускоряет рост правил за счет предварительно скомпилированных regex, нормализованных токенов, bounded normalization cache и легкого rule index. Full-scan mode остается для отладки и regression-сравнения.

Правила вынесены в конфиги:

- `configs/drive_classification_taxonomy.yml` - словарь статусов, объектов, подразделений, семейств документов и cleanup-категорий.
- `configs/drive_path_rules.yml` - path-first правила для объектов, отделов, источников и рабочих зон.
- `configs/drive_filename_rules.yml` - типы документов по имени файла.
- `configs/drive_extension_rules.yml` - fallback-классификация по расширению и MIME type.
- `configs/drive_sensitivity_rules.yml` - персональные, финансовые, договорные, HR и security-сигналы.
- `configs/drive_media_rules.yml` - фото, видео, аудио, design source, сканы и скриншоты.
- `configs/drive_cleanup_rules.yml` - системный мусор, временные файлы, архивы, дубли и кандидаты на ручной разбор.

В `inventory.csv` и Excel добавлены поля `classification_status`, `matched_path_rules`, `matched_filename_rules`, `matched_extension_rules`, `matched_sensitivity_rules`, `path_confidence`, `filename_confidence`, `extension_confidence`, `combined_confidence`, `conflict_flags`, `lifecycle_status`, `cleanup_category`, `source_origin`, `media_subtype`, `cloud_analysis_candidate`, `priority_for_human_review`.

Важное ограничение: Taxonomy V2 не утверждает финальную структуру папок и не выполняет переносы. Она готовит объяснимый реестр для ручной проверки, уточнения правил и следующего content/media/cloud-AI слоя.

## Как запустить локально

Сначала установите зависимости:

```bash
pip install -r requirements.txt
```

Минимальный тестовый прогон:

```bash
python -m knowledge_ops.drive_inventory \
  --scope all-accessible-drive \
  --config configs/drive_inventory.yml \
  --out-dir out/drive_inventory \
  --mode full \
  --skip-google-sheets true \
  --dry-run true \
  --max-files 100
```

Полный прогон после проверки тестового результата:

```bash
python -m knowledge_ops.drive_inventory \
  --scope all-accessible-drive \
  --config configs/drive_inventory.yml \
  --out-dir out/drive_inventory \
  --mode full \
  --skip-google-sheets true \
  --dry-run true \
  --max-files 0
```

Опциональные флаги:

- `--enable-content-inspection true` - извлекать ограниченный текстовый слой и применять rule engine.
- `--content-inspection-max-files 0` - лимит попыток content inspection; `0` означает без лимита, в GitHub Actions по умолчанию используется защитный лимит.
- `--content-char-limit 20000` - максимум символов текста для классификации.
- `--content-page-limit 20` - максимум страниц/слайдов для PDF/презентаций.
- `--max-download-size-mb 25` - максимум размера скачивания для content inspection.
- `--enable-ocr false` - OCR изображений и PDF без текстового слоя выключен по умолчанию; при `true` используется локальный Tesseract, без вызовов Cloud Vision API. В GitHub Actions Tesseract ставится workflow автоматически, локально его нужно установить отдельно.
- `--enable-excel-content-inspection true` - читать обычные XLSX, но не native Google Sheets.
- `--store-content-preview false` и `--store-sensitive-snippets false` - полный текст и чувствительные фрагменты не сохраняются.
- `--include-content-hash` - считать SHA-256 для обычных файлов в пределах `max_download_bytes`.
- `--include-google-export-hash` - считать export hash для Google Docs/Slides. Google Sheets всё равно исключаются.
- `--include-media-hash` - считать content hash для изображений и видео в пределах лимита.
- `--include-perceptual-image-hash` - зарезервирован как future mode без тяжёлых зависимостей.
- `--safe-mode true` - read-only guard, включён по умолчанию.

## Credentials

Используется существующая service account схема репозитория:

- `GOOGLE_SERVICE_ACCOUNT_JSON`, или
- `GOOGLE_APPLICATION_CREDENTIALS`,
- опционально `GOOGLE_DELEGATED_USER`.

Контур инвентаризации запрашивает только Drive read-only scope: `https://www.googleapis.com/auth/drive.readonly`.

## GitHub Actions

Workflow `Drive Inventory Pipeline` запускается только вручную через `workflow_dispatch`. Он выполняет инвентаризацию этапами и отдаёт результаты как artifacts:

- `drive-inventory-01-metadata`
- `drive-inventory-02-content-classification`
- `drive-inventory-03-final`
- `drive-inventory-04-ai-readiness`, если включён estimate-only AI readiness

Результаты не коммитятся в репозиторий.

В интерфейсе GitHub путь такой: `Actions` -> `Drive Inventory Pipeline` -> `Run workflow`.
Файл workflow лежит в `.github/workflows/drive-inventory.yml`, а настройки инвентаризации — в `configs/drive_inventory.yml`.
Старый путь `config/drive-inventory.yml` не используется.

## Отчёты

В `out/drive_inventory` создаются:

- `inventory.xlsx`
- `all_objects.csv`
- `all_objects_ru.csv`
- `inventory.csv`
- `inventory_ru.csv`
- `folders.csv`
- `folders_ru.csv`
- `skipped_google_sheets.csv`
- `skipped_google_sheets_ru.csv`
- `access_coverage.csv`
- `access_coverage_ru.csv`
- `exact_duplicates.csv`
- `exact_duplicates_ru.csv`
- `version_duplicate_candidates.csv`
- `version_duplicate_candidates_ru.csv`
- `semantic_duplicate_candidates.csv`
- `semantic_duplicate_candidates_ru.csv`
- `classification_review.csv`
- `classification_review_ru.csv`
- `sensitivity_review.csv`
- `sensitivity_review_ru.csv`
- `migration_decision_plan.csv`
- `migration_decision_plan_ru.csv`
- `content_inspection.csv`
- `content_inspection_ru.csv`
- `content_rule_matches.csv`
- `content_rule_matches_ru.csv`
- `content_sensitivity_flags.csv`
- `content_sensitivity_flags_ru.csv`
- `rule_match_summary.csv`
- `rule_match_summary_ru.csv`
- `object_classification_summary.csv`
- `object_classification_summary_ru.csv`
- `department_classification_summary.csv`
- `department_classification_summary_ru.csv`
- `document_type_summary.csv`
- `document_type_summary_ru.csv`
- `sensitivity_summary.csv`
- `sensitivity_summary_ru.csv`
- `cleanup_candidates.csv`
- `cleanup_candidates_ru.csv`
- `system_trash_candidates.csv`
- `system_trash_candidates_ru.csv`
- `exact_duplicate_groups.csv`
- `exact_duplicate_groups_ru.csv`
- `media_classification_summary.csv`
- `media_classification_summary_ru.csv`
- `unknown_after_v2.csv`
- `unknown_after_v2_ru.csv`
- `classification_performance.json`
- `classification_performance.md`
- `rule_performance.csv`
- `rule_performance_ru.csv`
- `zero_hit_rules.csv`
- `zero_hit_rules_ru.csv`
- `slow_rules.csv`
- `slow_rules_ru.csv`
- `suspicious_rules.csv`
- `suspicious_rules_ru.csv`
- `classification_quality_summary.csv`
- `classification_quality_summary_ru.csv`
- `classification_quality_summary.md`
- `classification_v3_inventory.csv`
- `classification_v3_review.csv`
- `classification_v3_unknown.csv`
- `classification_v3_conflicts.csv`
- `classification_v3_sensitivity.csv`
- `classification_v3_ocr_candidates.csv`
- `classification_v3_cloud_ai_candidates.csv`
- `classification_v3_duplicate_groups.csv`
- `classification_v3_media.csv`
- `classification_v3_human_review_queues.csv`
- `classification_v3_report.md`
- `OCR_readiness_report.md`
- `cloud_ai_approval_report.md`
- `human_review_guide.md`
- `drive_structure_tree.md`
- `audit_report.md`
- `run_log.jsonl`
- `errors.csv`
- `errors_ru.csv`

`inventory.xlsx` содержит листы Summary, All Objects, Inventory, Classification V2 Summary, Objects, Departments, Document Types, Sensitivity, Cleanup Candidates, System Trash, Media, Unknown After V2, Human Review Queues, OCR Candidates, Cloud AI Candidates, Conflicts, Rule Matches, Rule Performance, Quality Summary, Exact Duplicate Groups, Folders, Skipped Google Sheets, Exact Duplicates, Version Candidates, Semantic Candidates, Classification Review, Sensitivity Review, Migration Decision Plan, Content Inspection, Content Rule Matches, Content Sensitivity, Access Coverage и Errors.

Проверка правил без Drive-аудита:

```bash
python -m knowledge_ops.drive_inventory validate-rules \
  --config configs/drive_inventory.yml \
  --out-dir out/classification_engine_diagnostics
```

## Как читать статусы и дубли

- `SKIPPED_GOOGLE_SHEET` - Google Sheet был найден, но не тронут на уровне содержимого.
- `MARK_AS_CANONICAL_CANDIDATE` - вероятный главный экземпляр в группе дублей.
- `MARK_AS_DUPLICATE_CANDIDATE` - кандидат на дубль для ручного разбора.
- `SENSITIVE_REVIEW_REQUIRED` - файл попал в чувствительную зону: персональные данные, договоры, финансы, HR, безопасность и подобное.
- `REVIEW_REQUIRED` - требуется ручная проверка классификации или будущего решения.
- `extracted_pdf_text` - текст найден в PDF без OCR.
- `extracted_pdf_ocr` / `extracted_image_ocr` - текст получен локальным OCR.
- `pdf_no_text_layer` - PDF не дал текстового слоя, OCR не был включен.
- `ocr_unavailable` - OCR был включен, но runtime или Python-зависимости недоступны.
- `ocr_failed` / `ocr_no_text` - OCR попытка не дала пригодного текста.

`exact_duplicates.csv` основан на `md5Checksum + size`, `content_hash` или `export_hash`. `version_duplicate_candidates.csv` использует нормализацию имён и маркеры версий. `semantic_duplicate_candidates.csv` использует путь, название, тип и повторяющиеся номера договоров/актов/счетов без внешнего AI.

## Что инструмент НЕ делает

- Не удаляет файлы.
- Не перемещает файлы и папки.
- Не переименовывает объекты.
- Не создаёт ярлыки или папки.
- Не меняет права.
- Не меняет metadata в Drive.
- Не читает и не экспортирует Google Sheets.
- Не сохраняет полный текст документов или чувствительные snippets по умолчанию.
- Не даёт рекомендацию `DELETE` на первом этапе.

## Как использовать результаты

1. Сначала просмотреть `audit_report.md` и `inventory.xlsx`.
2. Отдельно разобрать `sensitivity_review.csv`.
3. Проверить группы из duplicate reports.
4. Использовать `migration_decision_plan.csv` как таблицу управленческих решений: заполнить human decision, approved_by, approved_at, final_location.
5. Только после ручной проверки проектировать следующий этап миграции или дедупликации.
