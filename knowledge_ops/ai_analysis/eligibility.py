from __future__ import annotations

from knowledge_ops.ai_analysis.models import AIFileRecord

IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "tiff", "tif", "bmp", "gif"}
VIDEO_EXT = {"mp4", "mov", "avi", "mkv", "webm", "m4v"}
AUDIO_EXT = {"mp3", "wav", "m4a", "aac", "flac", "ogg"}
DOC_EXT = {"pdf", "doc", "docx", "rtf", "txt", "html", "htm"}
PRESENTATION_EXT = {"ppt", "pptx"}
ARCHIVE_EXT = {"zip", "rar", "7z", "tar", "gz"}
DESIGN_EXT = {"psd", "ai", "indd", "fig", "sketch"}
SENSITIVE = {"owner_data", "guest_data", "employee_data", "personal_data", "legal_contract", "financial", "accounting", "HR", "commercial", "security"}


def classify_eligibility(record: AIFileRecord, max_file_size_mb: int = 200) -> AIFileRecord:
    ext = record.extension.lower()
    mime = record.mime_type.lower()
    reasons = []
    if record.is_google_sheet_skipped or mime == "application/vnd.google-apps.spreadsheet":
        record.eligibility_status = "SKIPPED_GOOGLE_SHEET"
        record.reason = "Native Google Sheets are never sent to Cloud AI."
        return record
    if record.duplicate_kind == "exact" and record.file_id != record.canonical_candidate_id:
        record.eligibility_status = "SKIPPED_DUPLICATE"
        record.reason = "Exact duplicate excluded; canonical candidate can represent the group."
        return record
    if record.size and record.size > max_file_size_mb * 1024 * 1024:
        record.eligibility_status = "SKIPPED_TOO_LARGE"
        record.reason = "File exceeds configured max cloud analysis size."
        return record
    if ext in ARCHIVE_EXT:
        record.eligibility_status = "LOCAL_ONLY_RECOMMENDED"
        record.reason = "Archive files stay metadata-only in the first AI preparation stage."
        return record
    if ext in DESIGN_EXT:
        record.eligibility_status = "LOCAL_ONLY_RECOMMENDED"
        record.reason = "Design sources stay metadata-only unless preview extraction is added."
        return record

    if ext in IMAGE_EXT or mime.startswith("image/"):
        record.eligible_services.append("vision")
        record.recommended_service = "vision"
        record.recommended_features = ["label_detection", "text_detection"]
        record.image_count_estimated = 1
    if ext == "pdf" or mime == "application/pdf":
        record.eligible_services.append("document_ai")
        record.recommended_service = record.recommended_service or "document_ai"
        record.recommended_features = ["enterprise_document_ocr"]
        record.page_count_estimated = record.page_count_exact or estimate_pages(record.size)
    if ext in DOC_EXT or mime.startswith("text/"):
        if record.content_extracted_locally:
            reasons.append("Local content extraction already available.")
        else:
            record.eligible_services.append("document_ai")
            record.recommended_service = record.recommended_service or "document_ai"
            record.recommended_features = ["enterprise_document_ocr"]
            record.page_count_estimated = record.page_count_estimated or estimate_pages(record.size)
    if ext in PRESENTATION_EXT:
        record.eligible_services.append("document_ai")
        record.recommended_service = record.recommended_service or "document_ai"
        record.recommended_features = ["layout_parser"]
        record.page_count_estimated = record.page_count_estimated or estimate_pages(record.size)
    if ext in VIDEO_EXT or mime.startswith("video/"):
        record.eligible_services.append("video_intelligence")
        record.recommended_service = record.recommended_service or "video_intelligence"
        record.recommended_features = ["label_detection", "shot_change_detection"]
        record.video_duration_seconds = record.video_duration_seconds or estimate_duration(record.size)
    if ext in AUDIO_EXT or mime.startswith("audio/"):
        record.eligible_services.append("speech_to_text")
        record.recommended_service = record.recommended_service or "speech_to_text"
        record.recommended_features = ["standard_batch"]
        record.audio_duration_seconds = record.audio_duration_seconds or estimate_duration(record.size)

    record.eligible_services = sorted(set(record.eligible_services))
    if not record.eligible_services:
        record.eligibility_status = "NOT_ELIGIBLE"
        record.reason = "No configured Cloud AI route for mime/extension."
        return record
    if record.sensitivity_suggestion in SENSITIVE:
        record.requires_manual_approval = True
        record.cloud_analysis_risk_level = "high"
        record.eligibility_status = "SKIPPED_SENSITIVE_REQUIRES_APPROVAL"
        reasons.append("Sensitive classification requires manual approval before Cloud AI.")
    else:
        record.cloud_analysis_risk_level = "medium" if record.recommended_service in {"video_intelligence", "speech_to_text"} else "low"
        record.eligibility_status = "CLOUD_RECOMMENDED"
    record.reason = "; ".join(reasons or ["Eligible by mime/extension routing."])
    return record


def estimate_pages(size: int) -> int:
    if not size:
        return 1
    return max(1, min(1000, int(size / 100_000) + 1))


def estimate_duration(size: int) -> int:
    if not size:
        return 60
    return max(30, min(4 * 60 * 60, int(size / 1_000_000) * 60))
