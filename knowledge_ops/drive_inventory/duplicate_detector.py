from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from knowledge_ops.drive_inventory.models import DriveInventoryItem
from knowledge_ops.drive_inventory.normalizer import extract_name_features, split_extension, strip_version_markers
from knowledge_ops.drive_inventory.safety import assert_safe_recommendation


def mark_duplicates(items: List[DriveInventoryItem]) -> Dict[str, List[DriveInventoryItem]]:
    groups: Dict[str, List[DriveInventoryItem]] = {}
    groups.update(mark_exact_duplicates(items))
    groups.update(mark_version_candidates(items))
    groups.update(mark_semantic_candidates(items))
    return groups


def mark_exact_duplicates(items: List[DriveInventoryItem]) -> Dict[str, List[DriveInventoryItem]]:
    buckets: Dict[str, List[DriveInventoryItem]] = defaultdict(list)
    for item in eligible_files(items):
        key = ""
        if item.md5_checksum and item.size is not None:
            key = f"md5:{item.md5_checksum}:{item.size}"
        elif item.content_hash:
            key = f"content:{item.content_hash}"
        elif item.export_hash:
            key = f"export:{item.export_hash}"
        if key:
            buckets[key].append(item)

    return apply_duplicate_groups(
        buckets,
        prefix="EXACT",
        duplicate_kind="exact",
        recommendation="MARK_AS_DUPLICATE_CANDIDATE",
        reason="Exact duplicate by checksum/hash metadata.",
    )


def mark_version_candidates(items: List[DriveInventoryItem]) -> Dict[str, List[DriveInventoryItem]]:
    buckets: Dict[str, List[DriveInventoryItem]] = defaultdict(list)
    for item in eligible_files(items):
        base, ext = split_extension(item.name, item.mime_type)
        key = f"{strip_version_markers(base)}:{ext or item.mime_type}:{item.object_suggestion}:{item.department_suggestion}"
        if len(key) > 10:
            buckets[key].append(item)
    return apply_duplicate_groups(
        buckets,
        prefix="VERSION",
        duplicate_kind="version_candidate",
        recommendation="MARK_AS_DUPLICATE_CANDIDATE",
        reason="Possible version duplicate by normalized filename/path classification.",
        overwrite_exact=False,
    )


def mark_semantic_candidates(items: List[DriveInventoryItem]) -> Dict[str, List[DriveInventoryItem]]:
    buckets: Dict[str, List[DriveInventoryItem]] = defaultdict(list)
    for item in eligible_files(items):
        features = extract_name_features(item.name, item.full_path)
        ids = features["contracts"] or features["acts"] or features["invoices"] or features["registries"]
        if not ids:
            continue
        key = "|".join(
            [
                item.object_suggestion,
                item.department_suggestion,
                item.document_type_suggestion,
                ",".join(ids),
                ",".join(features["years"]),
            ]
        )
        buckets[key].append(item)
    return apply_duplicate_groups(
        buckets,
        prefix="SEMANTIC",
        duplicate_kind="semantic_candidate",
        recommendation="REVIEW_REQUIRED",
        reason="Possible semantic duplicate by repeated document identifiers in names/paths; no external AI used.",
        overwrite_exact=False,
    )


def apply_duplicate_groups(
    buckets: Dict[str, List[DriveInventoryItem]],
    prefix: str,
    duplicate_kind: str,
    recommendation: str,
    reason: str,
    overwrite_exact: bool = True,
) -> Dict[str, List[DriveInventoryItem]]:
    assert_safe_recommendation(recommendation)
    result: Dict[str, List[DriveInventoryItem]] = {}
    index = 1
    for bucket_items in buckets.values():
        unique = {item.file_id: item for item in bucket_items}
        if len(unique) < 2:
            continue
        group_items = list(unique.values())
        canonical = choose_canonical(group_items)
        group_id = f"{prefix}-{index:05d}"
        index += 1
        result[group_id] = group_items
        for item in group_items:
            if item.duplicate_kind == "exact" and not overwrite_exact:
                continue
            item.duplicate_group_id = group_id
            item.duplicate_kind = duplicate_kind
            item.canonical_candidate_id = canonical.file_id
            if item.file_id == canonical.file_id:
                item.action_recommendation = "MARK_AS_CANONICAL_CANDIDATE"
                item.cleanup_category = "canonical_review"
                item.lifecycle_status = "canonical_candidate"
            else:
                item.action_recommendation = recommendation
                item.cleanup_category = (
                    "system_trash_candidate"
                    if item.cleanup_category == "system_trash_candidate" or item.sensitivity_suggestion == "system_trash"
                    else "duplicate_review"
                )
                item.lifecycle_status = "exact_duplicate_candidate" if duplicate_kind == "exact" else "duplicate_candidate"
            if duplicate_kind == "exact" and item.classification_status != "CLASSIFIED_SYSTEM_TRASH":
                item.classification_status = "CLASSIFIED_METADATA_MEDIUM"
            item.reason = append_reason(item.reason, reason)
    return result


def choose_canonical(items: List[DriveInventoryItem]) -> DriveInventoryItem:
    return sorted(
        items,
        key=lambda item: (
            item.modified_time or "",
            int(item.size or 0),
            item.name.lower(),
        ),
        reverse=True,
    )[0]


def eligible_files(items: Iterable[DriveInventoryItem]) -> Iterable[DriveInventoryItem]:
    return (
        item
        for item in items
        if item.object_kind == "file" and not item.is_google_sheet_skipped and not item.trashed
    )


def append_reason(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing}; {addition}"
