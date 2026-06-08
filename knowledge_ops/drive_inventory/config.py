from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass(frozen=True)
class InventoryConfig:
    scope: str = "all-accessible-drive"
    root_folder_id: Optional[str] = None
    page_size: int = 1000
    max_download_bytes: int = 10 * 1024 * 1024
    skip_google_sheets: bool = True
    include_content_hash: bool = False
    include_google_export_hash: bool = False
    include_media_hash: bool = False
    include_perceptual_image_hash: bool = False
    enable_content_inspection: bool = True
    content_char_limit: int = 20000
    content_page_limit: int = 20
    max_download_size_mb: int = 25
    enable_ocr: bool = False
    enable_excel_content_inspection: bool = True
    store_content_preview: bool = False
    store_sensitive_snippets: bool = False
    content_rules_config: str = "configs/drive_content_rules.yml"
    safe_mode: bool = True
    cache_dir: str = ".cache/drive_inventory"

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "InventoryConfig":
        inventory = data.get("drive_inventory", data)
        return cls(
            scope=inventory.get("scope", cls.scope),
            root_folder_id=inventory.get("root_folder_id"),
            page_size=int(inventory.get("page_size", cls.page_size)),
            max_download_bytes=int(inventory.get("max_download_bytes", cls.max_download_bytes)),
            skip_google_sheets=as_bool(inventory.get("skip_google_sheets", cls.skip_google_sheets)),
            include_content_hash=as_bool(inventory.get("include_content_hash", cls.include_content_hash)),
            include_google_export_hash=as_bool(inventory.get("include_google_export_hash", cls.include_google_export_hash)),
            include_media_hash=as_bool(inventory.get("include_media_hash", cls.include_media_hash)),
            include_perceptual_image_hash=as_bool(
                inventory.get("include_perceptual_image_hash", cls.include_perceptual_image_hash)
            ),
            enable_content_inspection=as_bool(inventory.get("enable_content_inspection", cls.enable_content_inspection)),
            content_char_limit=int(inventory.get("content_char_limit", cls.content_char_limit)),
            content_page_limit=int(inventory.get("content_page_limit", cls.content_page_limit)),
            max_download_size_mb=int(inventory.get("max_download_size_mb", cls.max_download_size_mb)),
            enable_ocr=as_bool(inventory.get("enable_ocr", cls.enable_ocr)),
            enable_excel_content_inspection=as_bool(
                inventory.get("enable_excel_content_inspection", cls.enable_excel_content_inspection)
            ),
            store_content_preview=as_bool(inventory.get("store_content_preview", cls.store_content_preview)),
            store_sensitive_snippets=as_bool(
                inventory.get("store_sensitive_snippets", cls.store_sensitive_snippets)
            ),
            content_rules_config=inventory.get("content_rules_config", cls.content_rules_config),
            safe_mode=as_bool(inventory.get("safe_mode", cls.safe_mode)),
            cache_dir=inventory.get("cache_dir", cls.cache_dir),
        )


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def load_inventory_config(path: str | Path | None) -> InventoryConfig:
    if not path:
        return InventoryConfig()
    config_path = Path(path)
    if not config_path.exists() and str(config_path).replace("\\", "/") == "configs/drive_inventory.yml":
        fallback = Path("config/drive-inventory.yml")
        if fallback.exists():
            config_path = fallback
    if not config_path.exists():
        return InventoryConfig()
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return InventoryConfig.from_mapping(data)
