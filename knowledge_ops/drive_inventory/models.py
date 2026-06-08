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
    "department_suggestion",
    "function_suggestion",
    "document_family_suggestion",
    "document_type_suggestion",
    "process_suggestion",
    "audience_suggestion",
    "sensitivity_suggestion",
    "retention_suggestion",
    "duplicate_group_id",
    "duplicate_kind",
    "canonical_candidate_id",
    "action_recommendation",
    "confidence",
    "reason",
    "human_decision",
    "final_location",
    "comment",
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
    department_suggestion: str = "не определено"
    function_suggestion: str = "не определено"
    document_family_suggestion: str = "неизвестно"
    document_type_suggestion: str = "неизвестно"
    process_suggestion: str = "не определено"
    audience_suggestion: str = "не определено"
    sensitivity_suggestion: str = "unknown"
    retention_suggestion: str = "review"
    duplicate_group_id: str = ""
    duplicate_kind: str = ""
    canonical_candidate_id: str = ""
    action_recommendation: str = "REVIEW_REQUIRED"
    confidence: str = "low"
    reason: str = ""
    human_decision: str = ""
    final_location: str = ""
    comment: str = ""

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
