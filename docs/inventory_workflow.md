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
| `generate_ai_estimate` | Считать оценку будущего Cloud AI-анализа | `true` |

Secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON` — обязателен для GitHub Actions.
- `GOOGLE_DELEGATED_USER` — опционален.

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

- `inventory.csv`
- `inventory_ru.csv`
- `folders.csv`
- `folders_ru.csv`
- `skipped_google_sheets.csv`
- `skipped_google_sheets_ru.csv`
- первичный `audit_report.md`

Этот этап нужен для ранней диагностики доступа, масштаба и MIME-распределения.

## Этап 02 — content classification

Цель: улучшить классификацию за счет ограниченного текстового слоя.

Ограничения:

- Google Sheets всегда пропускаются.
- OCR выключен.
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
- отчеты по точным дублям;
- кандидаты на версионные и смысловые дубли;
- sensitivity review;
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
4. Полный metadata-only прогон: `max_files=0`, content inspection выключен.
5. Полный финальный прогон с content inspection только после проверки лимитов и времени выполнения.

## Что workflow не делает

- Не создает папки.
- Не переносит файлы.
- Не переименовывает объекты.
- Не меняет права.
- Не удаляет и не отправляет в корзину.
- Не пишет metadata обратно в Google Drive.
- Не запускает Cloud AI API.
