from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

FOLDER_MIME = "application/vnd.google-apps.folder"
SHEETS_MIME = "application/vnd.google-apps.spreadsheet"
DOCS_MIME = "application/vnd.google-apps.document"
SLIDES_MIME = "application/vnd.google-apps.presentation"

INVENTORY_COLUMNS = [
    "file_id",
    "name",
    "normalized_name",
    "mime_type",
    "object_kind",
    "extension",
    "size",
    "md5_checksum",
    "content_hash",
    "export_hash",
    "image_perceptual_hash",
    "web_view_link",
    "created_time",
    "modified_time",
    "viewed_by_me_time",
    "owners",
    "last_modifying_user",
    "parents",
    "full_path",
    "depth",
    "drive_id",
    "shared_drive_name",
    "trashed",
    "starred",
    "shared",
    "permissions_summary",
    "is_google_workspace_native",
    "is_google_sheet_skipped",
    "skip_reason",
    "object_suggestion",
    "object_confidence",
    "object_evidence",
    "department_suggestion",
    "department_confidence",
    "department_evidence",
    "function_suggestion",
    "function_confidence",
    "function_evidence",
    "document_family_suggestion",
    "document_family_confidence",
    "document_family_evidence",
    "document_type_suggestion",
    "document_type_confidence",
    "document_type_evidence",
    "process_suggestion",
    "process_confidence",
    "process_evidence",
    "audience_suggestion",
    "audience_confidence",
    "sensitivity_suggestion",
    "sensitivity_flags",
    "sensitivity_confidence",
    "sensitivity_evidence",
    "retention_suggestion",
    "classification_status",
    "matched_path_rules",
    "matched_filename_rules",
    "matched_extension_rules",
    "matched_sensitivity_rules",
    "matched_media_rules",
    "matched_cleanup_rules",
    "path_confidence",
    "filename_confidence",
    "extension_confidence",
    "combined_confidence",
    "conflict_flags",
    "lifecycle_status",
    "lifecycle_confidence",
    "lifecycle_evidence",
    "cleanup_category",
    "cleanup_confidence",
    "cleanup_evidence",
    "source_origin",
    "source_origin_confidence",
    "path_context_valid",
    "path_confidence_multiplier",
    "media_subtype",
    "media_subtype_confidence",
    "image_subtype",
    "video_subtype",
    "audio_subtype",
    "design_source_subtype",
    "cloud_analysis_candidate",
    "cloud_analysis_recommended_service",
    "cloud_analysis_approval_required",
    "priority_for_human_review",
    "human_review_queue",
    "classification_reason",
    "unit_number_detected",
    "premise_number_detected",
    "contract_number_detected",
    "act_number_detected",
    "invoice_number_detected",
    "payment_order_number_detected",
    "cadastral_number_detected",
    "date_detected",
    "year_detected",
    "month_detected",
    "corpus_detected",
    "legal_entity_marker_detected",
    "INN_detected",
    "KPP_detected",
    "OGRN_detected",
    "BIK_detected",
    "bank_account_detected",
    "phone_detected",
    "email_detected",
    "passport_marker_detected",
    "SNILS_detected",
    "ocr_candidate",
    "ocr_attempted",
    "ocr_engine",
    "ocr_status",
    "ocr_page_count",
    "ocr_text_hash",
    "ocr_text_length",
    "ocr_rule_matches",
    "ocr_sensitivity_flags",
    "ocr_document_type_suggestion",
    "ocr_confidence",
    "ocr_reason",
    "ocr_requires_manual_review",
    "duplicate_group_id",
    "duplicate_kind",
    "canonical_candidate_id",
    "action_recommendation",
    "confidence",
    "reason",
    "human_decision",
    "final_location",
    "comment",
    "content_inspection_enabled",
    "content_extracted",
    "content_extract_status",
    "content_extract_error",
    "content_length",
    "content_text_hash",
    "content_language_guess",
    "content_rule_matches",
    "content_regex_matches_count",
    "content_classification_boost",
    "content_sensitivity_flags",
    "content_based_document_type",
    "content_based_department",
    "content_based_process",
    "content_based_object",
    "content_based_audience",
    "content_based_confidence",
    "content_based_reason",
]


@dataclass
class DriveInventoryItem:
    file_id: str
    name: str
    normalized_name: str
    mime_type: str
    object_kind: str
    extension: str = ""
    size: Optional[int] = None
    md5_checksum: str = ""
    content_hash: str = ""
    export_hash: str = ""
    image_perceptual_hash: str = ""
    web_view_link: str = ""
    created_time: str = ""
    modified_time: str = ""
    viewed_by_me_time: str = ""
    owners: str = ""
    last_modifying_user: str = ""
    parents: str = ""
    full_path: str = ""
    depth: int = 0
    drive_id: str = ""
    shared_drive_name: str = ""
    trashed: bool = False
    starred: bool = False
    shared: bool = False
    permissions_summary: str = ""
    is_google_workspace_native: bool = False
    is_google_sheet_skipped: bool = False
    skip_reason: str = ""
    object_suggestion: str = "объект не определён"
    object_confidence: str = "unknown"
    object_evidence: str = ""
    department_suggestion: str = "не определено"
    department_confidence: str = "unknown"
    department_evidence: str = ""
    function_suggestion: str = "не определено"
    function_confidence: str = "unknown"
    function_evidence: str = ""
    document_family_suggestion: str = "неизвестно"
    document_family_confidence: str = "unknown"
    document_family_evidence: str = ""
    document_type_suggestion: str = "неизвестно"
    document_type_confidence: str = "unknown"
    document_type_evidence: str = ""
    process_suggestion: str = "не определено"
    process_confidence: str = "unknown"
    process_evidence: str = ""
    audience_suggestion: str = "не определено"
    audience_confidence: str = "unknown"
    sensitivity_suggestion: str = "unknown"
    sensitivity_flags: str = ""
    sensitivity_confidence: str = "unknown"
    sensitivity_evidence: str = ""
    retention_suggestion: str = "review"
    classification_status: str = "UNKNOWN"
    matched_path_rules: str = ""
    matched_filename_rules: str = ""
    matched_extension_rules: str = ""
    matched_sensitivity_rules: str = ""
    matched_media_rules: str = ""
    matched_cleanup_rules: str = ""
    path_confidence: str = ""
    filename_confidence: str = ""
    extension_confidence: str = ""
    combined_confidence: str = "unknown"
    conflict_flags: str = ""
    lifecycle_status: str = "unknown"
    lifecycle_confidence: str = "unknown"
    lifecycle_evidence: str = ""
    cleanup_category: str = "unknown_review"
    cleanup_confidence: str = "unknown"
    cleanup_evidence: str = ""
    source_origin: str = "unknown_origin"
    source_origin_confidence: str = "unknown"
    path_context_valid: bool = True
    path_confidence_multiplier: float = 1.0
    media_subtype: str = ""
    media_subtype_confidence: str = "unknown"
    image_subtype: str = ""
    video_subtype: str = ""
    audio_subtype: str = ""
    design_source_subtype: str = ""
    cloud_analysis_candidate: bool = False
    cloud_analysis_recommended_service: str = ""
    cloud_analysis_approval_required: bool = False
    priority_for_human_review: str = "normal"
    human_review_queue: str = "unknown_classification_review"
    classification_reason: str = ""
    unit_number_detected: str = ""
    premise_number_detected: str = ""
    contract_number_detected: str = ""
    act_number_detected: str = ""
    invoice_number_detected: str = ""
    payment_order_number_detected: str = ""
    cadastral_number_detected: str = ""
    date_detected: str = ""
    year_detected: str = ""
    month_detected: str = ""
    corpus_detected: str = ""
    legal_entity_marker_detected: str = ""
    INN_detected: str = ""
    KPP_detected: str = ""
    OGRN_detected: str = ""
    BIK_detected: str = ""
    bank_account_detected: str = ""
    phone_detected: str = ""
    email_detected: str = ""
    passport_marker_detected: str = ""
    SNILS_detected: str = ""
    ocr_candidate: bool = False
    ocr_attempted: bool = False
    ocr_engine: str = "disabled"
    ocr_status: str = "not_attempted"
    ocr_page_count: int = 0
    ocr_text_hash: str = ""
    ocr_text_length: int = 0
    ocr_rule_matches: str = ""
    ocr_sensitivity_flags: str = ""
    ocr_document_type_suggestion: str = ""
    ocr_confidence: str = "unknown"
    ocr_reason: str = ""
    ocr_requires_manual_review: bool = False
    duplicate_group_id: str = ""
    duplicate_kind: str = ""
    canonical_candidate_id: str = ""
    action_recommendation: str = "REVIEW_REQUIRED"
    confidence: str = "low"
    reason: str = ""
    human_decision: str = ""
    final_location: str = ""
    comment: str = ""
    content_inspection_enabled: bool = False
    content_extracted: bool = False
    content_extract_status: str = "not_attempted"
    content_extract_error: str = ""
    content_length: int = 0
    content_text_hash: str = ""
    content_language_guess: str = ""
    content_rule_matches: str = ""
    content_regex_matches_count: int = 0
    content_classification_boost: str = ""
    content_sensitivity_flags: str = ""
    content_based_document_type: str = ""
    content_based_department: str = ""
    content_based_process: str = ""
    content_based_object: str = ""
    content_based_audience: str = ""
    content_based_confidence: str = ""
    content_based_reason: str = ""

    @classmethod
    def from_drive_file(cls, file_obj: Dict[str, Any], normalized_name: str, extension: str) -> "DriveInventoryItem":
        mime_type = file_obj.get("mimeType", "")
        is_folder = mime_type == FOLDER_MIME
        is_sheet = mime_type == SHEETS_MIME
        owners = compact_users(file_obj.get("owners", []))
        last_modifying_user = compact_user(file_obj.get("lastModifyingUser", {}))
        return cls(
            file_id=file_obj.get("id", ""),
            name=file_obj.get("name", ""),
            normalized_name=normalized_name,
            mime_type=mime_type,
            object_kind="folder" if is_folder else "skipped_google_sheet" if is_sheet else "file",
            extension=extension,
            size=int(file_obj["size"]) if str(file_obj.get("size", "")).isdigit() else None,
            md5_checksum=file_obj.get("md5Checksum", ""),
            web_view_link=file_obj.get("webViewLink", ""),
            created_time=file_obj.get("createdTime", ""),
            modified_time=file_obj.get("modifiedTime", ""),
            viewed_by_me_time=file_obj.get("viewedByMeTime", ""),
            owners=owners,
            last_modifying_user=last_modifying_user,
            parents=";".join(file_obj.get("parents", [])),
            drive_id=file_obj.get("driveId", ""),
            trashed=bool(file_obj.get("trashed", False)),
            starred=bool(file_obj.get("starred", False)),
            shared=bool(file_obj.get("shared", False)),
            permissions_summary=summarize_permissions(file_obj),
            is_google_workspace_native=mime_type.startswith("application/vnd.google-apps."),
            is_google_sheet_skipped=is_sheet,
            skip_reason="Google Sheets are skipped by first-stage audit policy." if is_sheet else "",
            action_recommendation="SKIPPED_GOOGLE_SHEET" if is_sheet else "REVIEW_REQUIRED",
            reason="Google Sheet metadata only; content/export/hash/classification skipped." if is_sheet else "",
        )

    def to_row(self) -> Dict[str, Any]:
        return {column: getattr(self, column) for column in INVENTORY_COLUMNS}


def compact_user(user: Dict[str, Any]) -> str:
    if not user:
        return ""
    return user.get("displayName") or user.get("emailAddress", "")


def compact_users(users: List[Dict[str, Any]]) -> str:
    return "; ".join(filter(None, (compact_user(user) for user in users)))


def summarize_permissions(file_obj: Dict[str, Any]) -> str:
    capabilities = file_obj.get("capabilities", {})
    flags = []
    if file_obj.get("shared"):
        flags.append("shared")
    if capabilities.get("canEdit"):
        flags.append("service_account_can_edit")
    if capabilities.get("canShare"):
        flags.append("service_account_can_share")
    if capabilities.get("canDelete"):
        flags.append("service_account_can_delete")
    return ";".join(flags)
