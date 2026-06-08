from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from knowledge_ops.drive_inventory.models import DriveInventoryItem


def folder_statistics(items: List[DriveInventoryItem]) -> List[Dict[str, str]]:
    children_by_parent: Dict[str, List[DriveInventoryItem]] = defaultdict(list)
    folders = {item.file_id: item for item in items if item.object_kind == "folder"}
    for item in items:
        for parent in filter(None, item.parents.split(";")):
            children_by_parent[parent].append(item)

    rows: List[Dict[str, str]] = []
    for folder_id, folder in folders.items():
        children = children_by_parent.get(folder_id, [])
        file_count = sum(1 for child in children if child.object_kind == "file")
        subfolder_count = sum(1 for child in children if child.object_kind == "folder")
        mime_types = Counter(child.mime_type for child in children if child.object_kind == "file")
        chaos = []
        if len(mime_types) > 5:
            chaos.append("mixed_types")
        if any(child.duplicate_group_id for child in children):
            chaos.append("duplicates")
        if any(child.sensitivity_suggestion not in {"unknown", "operational", "media"} for child in children):
            chaos.append("sensitive")
        if any(child.document_type_suggestion == "неизвестно" for child in children):
            chaos.append("unknown_files")
        rows.append(
            {
                "file_id": folder.file_id,
                "name": folder.name,
                "full_path": folder.full_path,
                "depth": str(folder.depth),
                "file_count": str(file_count),
                "subfolder_count": str(subfolder_count),
                "top_mime_types": "; ".join(f"{mime}:{count}" for mime, count in mime_types.most_common(5)),
                "chaos_signals": ";".join(chaos),
            }
        )
    return sorted(rows, key=lambda row: (int(row["depth"]), row["full_path"]))
