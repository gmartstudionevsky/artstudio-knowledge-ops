# Classification V3 / Deep Classification Layer

Classification V3 is a staged classification pipeline for ARTSTUDIO / RBI PM Drive inventory. This PR implements the first safe layer: taxonomy V3, metadata classification, regex entity extraction, V3 merge fields, OCR/cloud candidates, review queues and reports.

It does not move, rename, delete or edit Google Drive files. It does not read native Google Sheets. It does not call Cloud Vision, Document AI, Video Intelligence or Speech-to-Text.

## Layers

- Layer 0: inventory metadata from Drive.
- Layer 1: path, filename, extension, sensitivity, media, cleanup and lifecycle rules.
- Layer 2: existing text content inspection for supported safe formats.
- Layer 3: OCR candidate orchestration only. OCR is not enabled by default.
- Layer 4: media candidate classification from metadata/rules.
- Layer 5: Cloud AI readiness and approval flags only.
- Layer 6: final merge into confidence, conflict and human-review fields.

## V3.1 Real Drive Pattern Rules

V3.1 expands metadata-only rules with real Drive patterns from the first meta map while keeping the stage read-only. It does not add new OCR, Cloud Vision, Document AI or apply operations.

The main hardening points are:

- risky short abbreviations such as `АД`, `РД`, `ДД`, `КУ` and `КП` are not used as free substring tokens;
- stable short document codes such as `ДКП`, `ДДУ`, `АПП`, `УПД`, `ППР`, `РКО`, `БИК` and `ИНН` are treated as approved domain codes;
- Sales contract paths are kept separate from owner-contract paths unless owner context is explicit;
- Front Office owner-document folders, Housekeeping daily report paths, ChatExport files, system trash and signature/stamp assets have priority overrides;
- content rules use taxonomy-compatible values such as `service_contract`, `acceptance_transfer_act`, `invoice`, `UPD`, `owner_EGRN_extract`, `cleaning_checklist`, `timesheet`, `brandbook` and `consumer_corner_document`.

## ARTSTUDIO Base Guard

The `/ARTSTUDIO/` folder from the first meta map is treated as an auto-structured staging base, not as a reliable business taxonomy. Its subfolders, including `04_Standards_SOP`, `06_OTA`, `08_Legal_Files`, `09_Owner_Investor`, `02_Brand_Context` and `03_Object_Data`, are ignored as strong business context.

For files inside `/ARTSTUDIO/`, classification must primarily rely on filename, extension, MIME metadata, regex extraction, content inspection, later OCR/content layers and duplicate context. The inventory records:

- `source_origin=auto_structured_artstudio_base`
- `path_context_valid=false`
- `path_confidence_multiplier=0.0`
- `classification_reason` includes: `ARTSTUDIO base path ignored as business context because it was auto-structured before analysis.`

The V3 report also exposes:

- `auto_structured_artstudio_base_count`
- `files_inside_artstudio_base_with_invalid_path_context`
- `files_classified_by_filename_inside_artstudio_base`
- `files_classified_by_content_inside_artstudio_base`
- `files_still_unknown_inside_artstudio_base`

## Core Fields

V3 adds confidence/evidence fields for object, department, function, document family, document type, process, sensitivity, lifecycle, cleanup and media subtype. It also adds:

- `sensitivity_flags`
- `human_review_queue`
- `classification_reason`
- regex entity detections such as contract, act, invoice, cadastral number, INN, KPP, OGRN, BIK, phone, email and bank account
- `ocr_candidate` and OCR planning fields
- `cloud_analysis_recommended_service`
- `cloud_analysis_approval_required`

## Review Queues

Queues are not actions. They are manual review buckets:

- legal_review
- owner_contract_review
- finance_review
- HR_review
- sensitive_data_review
- media_publication_review
- brand_review
- system_trash_review
- duplicate_review
- cloud_ai_approval_review
- unknown_classification_review
- conflict_review
- OCR_review
- knowledge_base_review
- structure_review

## Reports

Main V3 outputs:

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

## Quality Checks

After every rule update, compare:

- unknown object/department/document-type rates
- conflict rate
- sensitive unknown rate
- OCR candidate count
- cloud approval count
- human-review queue distribution
- zero-hit and slow rules
- indexed/full-scan equivalence tests

The first V3 implementation intentionally avoids massive business-rule expansion. Rules should now be added iteratively, validated by reports and regression tests.
