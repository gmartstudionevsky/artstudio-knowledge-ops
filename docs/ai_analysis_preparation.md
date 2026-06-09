# Подготовка AI-анализа и оценка стоимости

## Зачем нужен слой

`knowledge_ops.ai_analysis` готовит следующий этап анализа содержимого через Google Cloud AI, но не запускает его. Модуль читает результаты Drive inventory, определяет пригодность файлов для Cloud Vision AI, Document AI, Video Intelligence и Speech-to-Text, считает billable units и примерную стоимость по сценариям.

Сначала нужен расчет, а не Cloud-анализ: так можно заранее понять объём, риски, чувствительные зоны, необходимость approval и бюджет.

## Что поддерживается

- Cloud Vision AI для изображений, сканов, скриншотов и OCR-кандидатов.
- Document AI для PDF, сканов и документов, где нужен OCR/layout.
- Video Intelligence для видео.
- Speech-to-Text для аудио и будущей обработки видео с аудиодорожкой.
- Локальный режим для дублей, архивов, design sources и файлов, уже хорошо классифицированных локально.
- Пропуск native Google Sheets, точных дублей не-канонических экземпляров, слишком больших файлов и sensitive-файлов без approval.

## Как считается стоимость

Цены лежат в `configs/ai_analysis_pricing.yml`. Код не хардкодит цены. Перед реальным запуском нужно проверить актуальные страницы Google Cloud Pricing и обновить YAML без изменения логики.

Сценарии:

- `metadata_only` — стоимость Cloud AI равна 0.
- `cheap` — ограниченный OCR/labels.
- `balanced` — разумный набор Vision/Document AI и выбранные медиа.
- `deep` — максимально широкий анализ eligible-файлов.
- `custom` — можно описать в routing config.

## Как запустить

```bash
python -m knowledge_ops.ai_analysis \
  --inventory out/drive_inventory/inventory.csv \
  --media-inventory out/drive_inventory/media_inventory.csv \
  --content-inspection out/drive_inventory/content_inspection.csv \
  --out-dir out/ai_analysis_estimate \
  --mode estimate \
  --pricing-config configs/ai_analysis_pricing.yml \
  --routing-config configs/ai_analysis_routing.yml \
  --dry-run true
```

Estimator намеренно падает, если `--inventory` отсутствует или пустой. Это защищает от успешных пустых отчетов в GitHub Actions. Для технической проверки пустого контура можно явно добавить `--allow-empty-inventory true`.

Проверка конфигов:

```bash
python -m knowledge_ops.ai_analysis \
  --mode validate-config \
  --pricing-config configs/ai_analysis_pricing.yml \
  --routing-config configs/ai_analysis_routing.yml \
  --dry-run true
```

## Выходные файлы

- `ai_readiness_inventory.csv`
- `cloud_eligibility.csv`
- `pricing_estimate.csv`
- `pricing_estimate.xlsx`
- `scenario_summary.csv`
- `service_units.csv`
- `budget_guard_report.csv`
- `ai_analysis_plan.csv`
- `ai_sample_plan.csv`
- `sensitive_cloud_review.csv`
- `skipped_for_cloud.csv`
- `cloud_setup_checklist.md`
- `ai_pricing_report.md`
- `run_log.jsonl`
- `errors.csv`

## Защитные ограничения

- Estimate mode не вызывает Cloud AI APIs.
- `AI_ANALYSIS_ALLOW_CLOUD_CALLS=false` по умолчанию.
- Загрузка чувствительных файлов отключена, если не задано `AI_ANALYSIS_ALLOW_SENSITIVE_UPLOAD=true`.
- Google Sheets всегда пропускаются.
- Точные дубли, которые не являются каноническими кандидатами, исключаются.
- HR/legal/owner/financial файлы требуют ручного approval.
- Budget guards помечают сценарии как `OVER_BUDGET` или `APPROVAL_REQUIRED`, а не запускают анализ.
- Проверяются не только деньги, но и лимиты объёма: изображения/страницы для Vision, страницы Document AI, минуты видео и аудио.
- Операции записи в Drive не реализованы.
- OCR-тексты, transcripts, thumbnails, keyframes и скачанные файлы не коммитятся.

## Чек-лист Google Cloud

Estimator пишет `cloud_setup_checklist.md`, где перечислены:

- Google Cloud project и billing.
- Cloud Vision API, Document AI API, Video Intelligence API, Speech-to-Text API, Cloud Storage API.
- IAM service account и secrets.
- Опциональный GCS staging bucket и lifecycle policy.
- Budget alerts, audit logs и data retention.
- Ручной approval перед sample/deep run.

## Будущий sample analysis

Текущая реализация только подготавливает guarded future mode `analyze-sample`. Реальные Cloud calls должны требовать:

- `--mode analyze-sample`;
- `AI_ANALYSIS_ALLOW_CLOUD_CALLS=true`;
- успешный budget guard;
- явный sample plan;
- отсутствие sensitive-файлов или `AI_ANALYSIS_ALLOW_SENSITIVE_UPLOAD=true`.
