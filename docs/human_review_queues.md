# Human Review Queues

Human review queues are triage labels for the next knowledge-base preparation step. They are not Drive actions.

## Queue Priority

The classifier assigns queues conservatively:

- cloud approval first when a sensitive file is a Cloud AI candidate;
- conflicts before ordinary classification review;
- system trash candidates into `system_trash_review`;
- legal/owner/finance/HR sensitive documents into specialized queues;
- OCR candidates into `OCR_review`;
- unknown files into `unknown_classification_review`;
- everything else into `knowledge_base_review`.

## Queues

- `legal_review`: legal or contract-sensitive documents.
- `owner_contract_review`: owner contracts, EGRN, cadastral and owner data.
- `finance_review`: financial, bank, accounting and tax data.
- `HR_review`: employee and HR documents.
- `sensitive_data_review`: duplicate or personal-data sensitive items.
- `media_publication_review`: media that may require publication review.
- `brand_review`: brand assets.
- `system_trash_review`: obvious system/temp files.
- `duplicate_review`: duplicate candidates.
- `cloud_ai_approval_review`: files requiring explicit approval before Cloud AI.
- `unknown_classification_review`: weakly classified or unknown files.
- `conflict_review`: conflicting metadata/content signals.
- `OCR_review`: OCR candidates not yet processed.
- `knowledge_base_review`: ordinary candidates for knowledge-base structuring.

## Reports

Use `classification_v3_human_review_queues.csv` and `human_review_guide.md` after every inventory run.
