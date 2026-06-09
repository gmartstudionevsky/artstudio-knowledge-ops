from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from knowledge_ops.drive_inventory.classifier import classify_item
from knowledge_ops.drive_inventory.config import InventoryConfig
from knowledge_ops.drive_inventory.content_inspector import (
    ContentInspector,
    ContentRuleEngine,
    apply_content_result,
)
from knowledge_ops.drive_inventory.drive_client import DriveInventoryClient
from knowledge_ops.drive_inventory.duplicate_detector import mark_duplicates
from knowledge_ops.drive_inventory.models import FOLDER_MIME, SHEETS_MIME, DriveInventoryItem
from knowledge_ops.drive_inventory.normalizer import normalize_name, split_extension


@dataclass
class InventoryResult:
    items: List[DriveInventoryItem]
    skipped_google_sheets: List[DriveInventoryItem]
    errors: List[Dict[str, str]] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat())
    scope: str = "all-accessible-drive"
    mode: str = "full"
    limitations: List[str] = field(default_factory=list)

    @property
    def folders(self) -> List[DriveInventoryItem]:
        return [item for item in self.items if item.object_kind == "folder"]

    @property
    def files(self) -> List[DriveInventoryItem]:
        return [item for item in self.items if item.object_kind == "file"]


class DriveInventoryScanner:
    def __init__(self, client: DriveInventoryClient, config: InventoryConfig):
        self.client = client
        self.config = config
        self.content_inspector = ContentInspector(
            client=client,
            config=config,
            rule_engine=ContentRuleEngine.from_file(config.content_rules_config),
        )

    def scan(self, scope: str, mode: str, root_folder_id: str = "", max_files: int = 0, run_log_path: Path | None = None) -> InventoryResult:
        result = InventoryResult(items=[], skipped_google_sheets=[], scope=scope, mode=mode)
        raw_files: List[Dict[str, Any]] = []
        iterator = (
            self.client.iter_folder_tree(root_folder_id, max_files=max_files)
            if scope in {"root", "folder"} and root_folder_id
            else self.client.iter_all_accessible(max_files=max_files)
        )
        for file_obj in iterator:
            raw_files.append(file_obj)
            self._log(run_log_path, {"event": "listed", "file_id": file_obj.get("id"), "name": file_obj.get("name")})

        path_map = build_paths(raw_files)
        content_inspection_attempts = 0
        for file_obj in raw_files:
            try:
                base_name, extension = split_extension(file_obj.get("name", ""), file_obj.get("mimeType", ""))
                item = DriveInventoryItem.from_drive_file(file_obj, normalize_name(base_name), extension)
                item.full_path = path_map.get(item.file_id, item.name)
                item.depth = max(0, item.full_path.count("/") - 1)
                if item.mime_type == SHEETS_MIME and self.config.skip_google_sheets:
                    result.skipped_google_sheets.append(item)
                    result.items.append(item)
                    continue
                if mode in {"classify", "full"}:
                    classify_item(item)
                if mode in {"classify", "full"} and self.config.enable_content_inspection and item.object_kind == "folder":
                    item.content_inspection_enabled = True
                    item.content_extract_status = "skipped_folder"
                elif mode in {"classify", "full"} and self.config.enable_content_inspection:
                    if (
                        self.config.content_inspection_max_files
                        and content_inspection_attempts >= self.config.content_inspection_max_files
                    ):
                        item.content_inspection_enabled = True
                        item.content_extract_status = "skipped_content_inspection_limit"
                    else:
                        content_inspection_attempts += 1
                        content_result = self.content_inspector.inspect(item, file_obj)
                        apply_content_result(item, content_result)
                if mode in {"inventory", "duplicates", "full"}:
                    self._maybe_hash(item, file_obj)
                result.items.append(item)
            except Exception as exc:
                error = {"file_id": file_obj.get("id", ""), "name": file_obj.get("name", ""), "error": str(exc)}
                result.errors.append(error)
                self._log(run_log_path, {"event": "error", **error})

        if mode in {"duplicates", "full"}:
            mark_duplicates(result.items)
        if self.config.include_perceptual_image_hash:
            result.limitations.append("Perceptual image hash is reserved for a future lightweight implementation.")
        return result

    def _maybe_hash(self, item: DriveInventoryItem, file_obj: Dict[str, Any]) -> None:
        if item.is_google_sheet_skipped or item.object_kind == "folder":
            return
        try:
            if self.config.include_content_hash or (self.config.include_media_hash and item.mime_type.startswith(("image/", "video/"))):
                item.content_hash = self.client.calculate_content_hash(file_obj)
            if self.config.include_google_export_hash:
                item.export_hash = self.client.calculate_export_hash(file_obj)
        except Exception as exc:
            item.comment = f"Hash skipped: {exc}"

    @staticmethod
    def _log(path: Path | None, payload: Dict[str, Any]) -> None:
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_paths(files: List[Dict[str, Any]]) -> Dict[str, str]:
    by_id = {file_obj.get("id", ""): file_obj for file_obj in files}
    path_cache: Dict[str, str] = {}

    def path_for(file_id: str, seen: set[str] | None = None) -> str:
        if file_id in path_cache:
            return path_cache[file_id]
        seen = seen or set()
        if file_id in seen:
            return by_id.get(file_id, {}).get("name", file_id)
        seen.add(file_id)
        file_obj = by_id.get(file_id)
        if not file_obj:
            return "Unknown"
        parents = file_obj.get("parents", [])
        name = file_obj.get("name", file_id)
        if not parents:
            path_cache[file_id] = f"/{name}"
            return path_cache[file_id]
        parent_id = parents[0]
        parent_path = path_for(parent_id, seen) if parent_id in by_id else f"/Unmapped parent {parent_id}"
        path_cache[file_id] = f"{parent_path.rstrip('/')}/{name}"
        return path_cache[file_id]

    for file_obj in files:
        path_for(file_obj.get("id", ""))
    return path_cache
