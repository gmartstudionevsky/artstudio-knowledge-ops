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
    content_inspection_max_files: int = 0
    content_char_limit: int = 20000
    content_page_limit: int = 20
    max_download_size_mb: int = 25
    enable_ocr: bool = False
    enable_image_ocr: bool = False
    enable_pdf_ocr: bool = False
    enable_presentation_ocr: bool = False
    enable_google_cloud_vision: bool = False
    enable_document_ai: bool = False
    ocr_max_files: int = 0
    ocr_max_pages_per_file: int = 10
    ocr_max_file_size_mb: int = 25
    ocr_only_for_review_queue: bool = True
    ocr_only_for_document_scan_candidates: bool = True
    ocr_allow_sensitive: bool = False
    ocr_store_text: bool = False
    ocr_store_sensitive_snippets: bool = False
    allow_sensitive_cloud_ai: bool = False
    allow_cloud_ai_calls: bool = False
    enable_excel_content_inspection: bool = True
    store_content_preview: bool = False
    store_sensitive_snippets: bool = False
    content_rules_config: str = "configs/drive_content_rules.yml"
    classification_taxonomy_config: str = "configs/drive_classification_taxonomy.yml"
    path_rules_config: str = "configs/drive_path_rules.yml"
    filename_rules_config: str = "configs/drive_filename_rules.yml"
    extension_rules_config: str = "configs/drive_extension_rules.yml"
    sensitivity_rules_config: str = "configs/drive_sensitivity_rules.yml"
    media_rules_config: str = "configs/drive_media_rules.yml"
    cleanup_rules_config: str = "configs/drive_cleanup_rules.yml"
    classification_use_rule_index: bool = True
    classification_strict_full_scan: bool = False
    classification_normalization_cache_size: int = 50000
    classification_slow_rule_ms: float = 2.0
    unknown_object_rate_max: float = 0.50
    unknown_department_rate_max: float = 0.50
    unknown_document_type_rate_max: float = 0.50
    conflict_rate_max: float = 0.10
    sensitive_unknown_rate_max: float = 0.30
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
            content_inspection_max_files=int(
                inventory.get("content_inspection_max_files", cls.content_inspection_max_files)
            ),
            content_char_limit=int(inventory.get("content_char_limit", cls.content_char_limit)),
            content_page_limit=int(inventory.get("content_page_limit", cls.content_page_limit)),
            max_download_size_mb=int(inventory.get("max_download_size_mb", cls.max_download_size_mb)),
            enable_ocr=as_bool(inventory.get("enable_ocr", cls.enable_ocr)),
            enable_image_ocr=as_bool(inventory.get("enable_image_ocr", cls.enable_image_ocr)),
            enable_pdf_ocr=as_bool(inventory.get("enable_pdf_ocr", cls.enable_pdf_ocr)),
            enable_presentation_ocr=as_bool(inventory.get("enable_presentation_ocr", cls.enable_presentation_ocr)),
            enable_google_cloud_vision=as_bool(inventory.get("enable_google_cloud_vision", cls.enable_google_cloud_vision)),
            enable_document_ai=as_bool(inventory.get("enable_document_ai", cls.enable_document_ai)),
            ocr_max_files=int(inventory.get("ocr_max_files", cls.ocr_max_files)),
            ocr_max_pages_per_file=int(inventory.get("ocr_max_pages_per_file", cls.ocr_max_pages_per_file)),
            ocr_max_file_size_mb=int(inventory.get("ocr_max_file_size_mb", cls.ocr_max_file_size_mb)),
            ocr_only_for_review_queue=as_bool(inventory.get("ocr_only_for_review_queue", cls.ocr_only_for_review_queue)),
            ocr_only_for_document_scan_candidates=as_bool(
                inventory.get("ocr_only_for_document_scan_candidates", cls.ocr_only_for_document_scan_candidates)
            ),
            ocr_allow_sensitive=as_bool(inventory.get("ocr_allow_sensitive", cls.ocr_allow_sensitive)),
            ocr_store_text=as_bool(inventory.get("ocr_store_text", cls.ocr_store_text)),
            ocr_store_sensitive_snippets=as_bool(
                inventory.get("ocr_store_sensitive_snippets", cls.ocr_store_sensitive_snippets)
            ),
            allow_sensitive_cloud_ai=as_bool(inventory.get("allow_sensitive_cloud_ai", cls.allow_sensitive_cloud_ai)),
            allow_cloud_ai_calls=as_bool(inventory.get("allow_cloud_ai_calls", cls.allow_cloud_ai_calls)),
            enable_excel_content_inspection=as_bool(
                inventory.get("enable_excel_content_inspection", cls.enable_excel_content_inspection)
            ),
            store_content_preview=as_bool(inventory.get("store_content_preview", cls.store_content_preview)),
            store_sensitive_snippets=as_bool(
                inventory.get("store_sensitive_snippets", cls.store_sensitive_snippets)
            ),
            content_rules_config=inventory.get("content_rules_config", cls.content_rules_config),
            classification_taxonomy_config=inventory.get(
                "classification_taxonomy_config", cls.classification_taxonomy_config
            ),
            path_rules_config=inventory.get("path_rules_config", cls.path_rules_config),
            filename_rules_config=inventory.get("filename_rules_config", cls.filename_rules_config),
            extension_rules_config=inventory.get("extension_rules_config", cls.extension_rules_config),
            sensitivity_rules_config=inventory.get("sensitivity_rules_config", cls.sensitivity_rules_config),
            media_rules_config=inventory.get("media_rules_config", cls.media_rules_config),
            cleanup_rules_config=inventory.get("cleanup_rules_config", cls.cleanup_rules_config),
            classification_use_rule_index=as_bool(
                inventory.get("classification_engine", {}).get(
                    "use_rule_index",
                    inventory.get("classification_use_rule_index", cls.classification_use_rule_index),
                )
            ),
            classification_strict_full_scan=as_bool(
                inventory.get("classification_engine", {}).get(
                    "strict_full_scan",
                    inventory.get("classification_strict_full_scan", cls.classification_strict_full_scan),
                )
            ),
            classification_normalization_cache_size=int(
                inventory.get("classification_engine", {}).get(
                    "normalization_cache_size",
                    inventory.get("classification_normalization_cache_size", cls.classification_normalization_cache_size),
                )
            ),
            classification_slow_rule_ms=float(
                inventory.get("classification_engine", {}).get(
                    "slow_rule_ms",
                    inventory.get("classification_slow_rule_ms", cls.classification_slow_rule_ms),
                )
            ),
            unknown_object_rate_max=float(inventory.get("quality_gates", {}).get("unknown_object_rate_max", cls.unknown_object_rate_max)),
            unknown_department_rate_max=float(
                inventory.get("quality_gates", {}).get("unknown_department_rate_max", cls.unknown_department_rate_max)
            ),
            unknown_document_type_rate_max=float(
                inventory.get("quality_gates", {}).get("unknown_document_type_rate_max", cls.unknown_document_type_rate_max)
            ),
            conflict_rate_max=float(inventory.get("quality_gates", {}).get("conflict_rate_max", cls.conflict_rate_max)),
            sensitive_unknown_rate_max=float(
                inventory.get("quality_gates", {}).get("sensitive_unknown_rate_max", cls.sensitive_unknown_rate_max)
            ),
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
    if not config_path.exists():
        return InventoryConfig()
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return InventoryConfig.from_mapping(data)
