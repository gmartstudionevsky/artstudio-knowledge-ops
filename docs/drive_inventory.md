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
- `--enable-ocr false` - OCR изображений выключен по умолчанию.
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

## Отчёты

В `out/drive_inventory` создаются:

- `inventory.xlsx`
- `inventory.csv`
- `inventory_ru.csv`
- `folders.csv`
- `folders_ru.csv`
- `skipped_google_sheets.csv`
- `skipped_google_sheets_ru.csv`
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
- `drive_structure_tree.md`
- `audit_report.md`
- `run_log.jsonl`
- `errors.csv`
- `errors_ru.csv`

`inventory.xlsx` содержит листы Summary, Inventory, Folders, Skipped Google Sheets, Exact Duplicates, Version Candidates, Semantic Candidates, Classification Review, Sensitivity Review, Migration Decision Plan, Content Inspection, Rule Matches, Content Sensitivity и Errors.

## Как читать статусы и дубли

- `SKIPPED_GOOGLE_SHEET` - Google Sheet был найден, но не тронут на уровне содержимого.
- `MARK_AS_CANONICAL_CANDIDATE` - вероятный главный экземпляр в группе дублей.
- `MARK_AS_DUPLICATE_CANDIDATE` - кандидат на дубль для ручного разбора.
- `SENSITIVE_REVIEW_REQUIRED` - файл попал в чувствительную зону: персональные данные, договоры, финансы, HR, безопасность и подобное.
- `REVIEW_REQUIRED` - требуется ручная проверка классификации или будущего решения.

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
