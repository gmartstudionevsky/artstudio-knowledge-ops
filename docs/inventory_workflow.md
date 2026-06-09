# Этапы инвентаризации Google Drive

## Зачем workflow разделен на этапы

Полный Drive может быть большим и неоднородным: Google Workspace native-файлы, PDF, Office, изображения, архивы, старые бинарные форматы и чувствительные документы. Один монолитный запуск либо слишком медленный, либо слишком грубый. Поэтому инвентаризация выполняется последовательными слоями.

Каждый этап дает самостоятельный артефакт и дополняет предыдущий:

1. Быстро получить карту объектов.
2. Ограниченно прочитать поддерживаемое содержимое.
3. Сформировать полный управленческий пакет отчетов.
4. Оценить, где в будущем может понадобиться Cloud AI и сколько это будет стоить.

## Где это находится в GitHub

- Раздел: `Actions`.
- Название workflow в UI: `Drive Inventory Pipeline`.
- Файл в репозитории: `.github/workflows/drive-inventory.yml`.
- Основной конфиг: `configs/drive_inventory.yml`.
- Ручной запуск: кнопка `Run workflow`.

Если workflow не виден в `Actions`, сначала проверьте, что открыта ветка `main` после merge PR с этим файлом. GitHub показывает workflow из default branch.

Параметры ручного запуска:

| Параметр | Назначение | Рекомендуемый первый запуск |
| --- | --- | --- |
| `scope` | Область сканирования Drive | `all-accessible-drive` |
| `root_folder_id` | ID корневой папки для `root`/`folder` | пусто |
| `max_files` | Максимум объектов на каждом этапе; `0` = без лимита | `100` |
| `content_inspection_max_files` | Максимум файлов для чтения содержимого | `25` |
| `content_char_limit` | Лимит извлеченного текста на файл | `20000` |
| `content_page_limit` | Лимит страниц PDF/слайдов | `20` |
| `max_download_size_mb` | Лимит размера скачивания для content inspection | `25` |
| `metadata_only_registry` | Запустить только полный metadata-only реестр всех видимых объектов | `false` |
| `enable_ocr` | Включить локальный OCR изображений и PDF без текстового слоя | `false` |
| `generate_ai_estimate` | Считать оценку будущего Cloud AI-анализа | `true` |

Secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON` — обязателен для GitHub Actions.
- `GOOGLE_DELEGATED_USER` — опционален.

## Рекомендуемые режимы запуска

### 1. Полный metadata-only реестр

Используйте, когда нужно сначала увидеть весь состав диска без скачивания файлов:

- `metadata_only_registry=true`
- `scope=all-accessible-drive`
- `root_folder_id=` пусто

В этом режиме workflow выполняет только этап `01 metadata map`, принудительно использует `max_files=0`, не читает содержимое и не запускает AI estimate. Главные артефакты: `all_objects.csv`, `inventory.csv`, `folders.csv`, `skipped_google_sheets.csv`, `access_coverage.csv`, `audit_report.md`, `inventory.xlsx`.

Metadata-only режим уже применяет Taxonomy V2 по путям, именам, расширениям, MIME type и служебным признакам. Для разбора состава Drive после такого прогона в первую очередь смотрите `object_classification_summary.csv`, `department_classification_summary.csv`, `document_type_summary.csv`, `sensitivity_summary.csv`, `rule_match_summary.csv`, `unknown_after_v2.csv`, `cleanup_candidates.csv`, `system_trash_candidates.csv` и листы `Classification V2 Summary`, `Objects`, `Departments`, `Document Types`, `Unknown After V2` в `inventory.xlsx`.

### 2. Ограниченный проверочный прогон

Используйте перед полной классификацией, чтобы проверить credentials, доступы, время выполнения и качество извлечения текста:

- `metadata_only_registry=false`
- `max_files=100`
- `content_inspection_max_files=25`
- `enable_ocr=false`
- `generate_ai_estimate=true`

### 3. Полная предварительная классификация

Используйте после проверки ограниченного прогона:

- `metadata_only_registry=false`
- `max_files=0`
- `content_inspection_max_files=0`
- `content_char_limit=20000` или выше, если нужно больше сигнала для правил
- `content_page_limit=20` или выше для длинных PDF/презентаций
- `max_download_size_mb=25` или выше, если много крупных PDF
- `enable_ocr=true`
- `generate_ai_estimate=true`

OCR выполняется локально в GitHub Actions через Tesseract и не вызывает Cloud Vision API. Если OCR runtime или поддержка конкретного файла недоступны, файл получает статус `ocr_unavailable`, `ocr_failed` или `ocr_no_text`, а инвентаризация продолжается.

## Этап 01 — metadata map

Цель: быстро понять состав Drive без скачивания содержимого.

Команда:

```bash
python -m knowledge_ops.drive_inventory \
  --mode inventory \
  --enable-content-inspection false \
  --skip-google-sheets true \
  --dry-run true
```

Результат:

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
- `rule_match_summary.csv`
- `object_classification_summary.csv`
- `department_classification_summary.csv`
- `document_type_summary.csv`
- `sensitivity_summary.csv`
- `unknown_after_v2.csv`
- первичный `audit_report.md`

Этот этап нужен для ранней диагностики доступа, масштаба, MIME-распределения и качества metadata-only классификации. Минимальные метрики для сравнения с первым прогоном: доля `UNKNOWN`, количество `CONFLICT_METADATA`, топ-20 path/filename rules, количество объектов по `object_suggestion`, распределение `cleanup_category`, количество `system_trash_candidate` и файлов с `cloud_analysis_candidate=true`.

## Этап 02 — content classification

Цель: улучшить классификацию за счет ограниченного текстового слоя.

Ограничения:

- Google Sheets всегда пропускаются.
- OCR включается только отдельным параметром `enable_ocr=true`.
- Полный текст не сохраняется.
- Чувствительные snippets не сохраняются.
- Количество попыток ограничено `content_inspection_max_files`.

Команда:

```bash
python -m knowledge_ops.drive_inventory \
  --mode classify \
  --enable-content-inspection true \
  --content-inspection-max-files 100 \
  --content-char-limit 20000 \
  --content-page-limit 20 \
  --max-download-size-mb 25 \
  --enable-ocr false \
  --store-content-preview false \
  --store-sensitive-snippets false \
  --dry-run true
```

Результат:

- `content_inspection.csv`
- `content_inspection_ru.csv`
- `content_rule_matches.csv`
- `content_rule_matches_ru.csv`
- `content_sensitivity_flags.csv`
- `content_sensitivity_flags_ru.csv`
- `classification_review.csv`
- `classification_review_ru.csv`
- `sensitivity_review.csv`
- `sensitivity_review_ru.csv`

## Этап 03 — final inventory reports

Цель: собрать итоговый пакет для управленческого разбора.

Команда:

```bash
python -m knowledge_ops.drive_inventory \
  --mode full \
  --enable-content-inspection true \
  --content-inspection-max-files 100 \
  --skip-google-sheets true \
  --dry-run true
```

Результат:

- полный inventory;
- полный all_objects registry, включая Google Sheets metadata-only;
- access coverage report для проверки полноты видимого scope;
- отчеты по точным дублям;
- кандидаты на версионные и смысловые дубли;
- sensitivity review;
- Taxonomy V2 summaries: объекты, подразделения, типы документов, чувствительность, медиа, unknown-after-v2, cleanup/system-trash candidates и rule match summary;
- migration decision plan как таблица будущих решений, не как план исполнения;
- `inventory.xlsx`;
- `audit_report.md`;
- `drive_structure_tree.md`.

## Этап 04 — AI readiness estimate

Цель: без Cloud API calls оценить пригодность файлов для будущего Cloud Vision, Document AI, Video Intelligence и Speech-to-Text.

Команда:

```bash
python -m knowledge_ops.ai_analysis \
  --inventory out/drive_inventory/03_final/inventory.csv \
  --content-inspection out/drive_inventory/03_final/content_inspection.csv \
  --out-dir out/ai_analysis_estimate \
  --mode estimate \
  --dry-run true
```

Результат:

- `cloud_eligibility.csv`
- `pricing_estimate.csv`
- `pricing_estimate.xlsx`
- `ai_analysis_plan.csv`
- `ai_sample_plan.csv`
- `sensitive_cloud_review.csv`
- `ai_pricing_report.md`
- `cloud_setup_checklist.md`

## Рекомендуемый темп

1. Первый прогон: `max_files=100`, `content_inspection_max_files=25`.
2. Проверка артефактов и ошибок доступа.
3. Средний прогон: `max_files=1000`, `content_inspection_max_files=100`.
4. Полный metadata-only прогон: `metadata_only_registry=true`.
5. Полный финальный прогон: `max_files=0`, `content_inspection_max_files=0`, `enable_ocr=true` только после проверки лимитов и времени выполнения.

## Что workflow не делает

- Не создает папки.
- Не переносит файлы.
- Не переименовывает объекты.
- Не меняет права.
- Не удаляет и не отправляет в корзину.
- Не пишет metadata обратно в Google Drive.
- Не запускает Cloud AI API.
