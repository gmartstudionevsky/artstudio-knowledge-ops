# OCR Pipeline

OCR is candidate-driven and disabled by default.

## Current Implementation

The inventory marks OCR candidates when metadata suggests a scan, screenshot, no-text PDF, or image-like document. It records:

- `ocr_candidate`
- `ocr_status`
- `ocr_reason`
- `ocr_requires_manual_review`
- `cloud_analysis_recommended_service`
- `cloud_analysis_approval_required`

No OCR text is stored by default.

## Guards

Config defaults:

```yaml
enable_ocr: false
enable_image_ocr: false
enable_pdf_ocr: false
enable_presentation_ocr: false
enable_google_cloud_vision: false
enable_document_ai: false
ocr_allow_sensitive: false
ocr_store_text: false
ocr_store_sensitive_snippets: false
allow_cloud_ai_calls: false
allow_sensitive_cloud_ai: false
```

Native Google Sheets are always skipped.

## Candidate Rules

OCR candidates include:

- PDFs without a text layer;
- image files named like scans, contracts, passports or acts;
- presentations with weak/no text extraction;
- unknown PDF/image/presentation files;
- sensitive legal/owner/finance/HR documents only as approval-required candidates.

## Next PR

The next OCR PR should add orchestration for local OCR sample runs behind explicit flags, page/file limits and sensitive approval checks. Cloud adapters should remain disabled until an explicit sample workflow is approved.
