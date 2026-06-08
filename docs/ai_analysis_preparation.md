# AI Analysis Preparation & Pricing Estimator

## Зачем нужен слой

`knowledge_ops.ai_analysis` готовит следующий этап анализа содержимого через Google Cloud AI, но не запускает его. Он читает результаты Drive inventory, определяет пригодность файлов для Cloud Vision AI, Document AI, Video Intelligence и Speech-to-Text, считает billable units и примерную стоимость по сценариям.

Сначала нужен estimate, а не cloud analysis, чтобы заранее понять объём, риски, sensitive approval и бюджет.

## Что поддерживается

- Cloud Vision AI для изображений, сканов, скриншотов и OCR-кандидатов.
- Document AI для PDF, сканов и документов, где нужен OCR/layout.
- Video Intelligence для видео.
- Speech-to-Text для аудио и будущей обработки видео с аудиодорожкой.
- Local-only для дублей, архивов, design sources и файлов, уже хорошо классифицированных локально.
- Skip для native Google Sheets, exact duplicate non-canonical files, слишком больших файлов и sensitive файлов без approval.

## Как считается стоимость

Цены лежат в `configs/ai_analysis_pricing.yml`. Код не хардкодит цены. Перед реальным запуском нужно проверить актуальные страницы Google Cloud Pricing и обновить YAML без изменения логики.

Сценарии:

- `metadata_only` - Cloud AI cost = 0.
- `cheap` - ограниченный OCR/labels.
- `balanced` - разумный набор Vision/Document AI и выбранные медиа.
- `deep` - максимально широкий анализ eligible файлов.
- `custom` - можно описать в routing config.

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

Config validation:

```bash
python -m knowledge_ops.ai_analysis \
  --mode validate-config \
  --pricing-config configs/ai_analysis_pricing.yml \
  --routing-config configs/ai_analysis_routing.yml \
  --dry-run true
```

## Outputs

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

## Safeguards

- Estimate mode does not call Cloud AI APIs.
- `AI_ANALYSIS_ALLOW_CLOUD_CALLS=false` by default.
- Sensitive upload is disabled unless `AI_ANALYSIS_ALLOW_SENSITIVE_UPLOAD=true`.
- Google Sheets are always skipped.
- Exact duplicate non-canonical files are excluded.
- Sensitive HR/legal/owner/financial files require manual approval.
- Budget guards mark scenarios as `OVER_BUDGET` instead of running analysis.
- No Drive write operations are implemented.
- No OCR text, transcripts, thumbnails, keyframes or downloaded files are committed.

## Google Cloud setup checklist

The estimator writes `cloud_setup_checklist.md`, covering:

- Google Cloud project and billing.
- Cloud Vision API, Document AI API, Video Intelligence API, Speech-to-Text API, Cloud Storage API.
- Service account IAM and secrets.
- Optional GCS staging bucket and lifecycle policy.
- Budget alerts, audit logs and data retention.
- Manual approval before sample/deep runs.

## Future sample analysis

The current implementation prepares `analyze-sample` as a guarded future mode only. Real Cloud calls must require:

- `--mode analyze-sample`;
- `AI_ANALYSIS_ALLOW_CLOUD_CALLS=true`;
- passed budget guard;
- explicit sample plan;
- no sensitive files unless `AI_ANALYSIS_ALLOW_SENSITIVE_UPLOAD=true`.
