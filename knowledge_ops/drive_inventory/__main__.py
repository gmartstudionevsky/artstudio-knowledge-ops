from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List, Optional

from knowledge_ops.drive_inventory.auth import build_read_only_drive_service
from knowledge_ops.drive_inventory.config import as_bool, load_inventory_config
from knowledge_ops.drive_inventory.classifier import write_rule_validation_reports
from knowledge_ops.drive_inventory.drive_client import DriveInventoryClient
from knowledge_ops.drive_inventory.report_writer import write_reports
from knowledge_ops.drive_inventory.scanner import DriveInventoryScanner


DEFAULT_CONFIG_PATH = "configs/drive_inventory.yml"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only ARTSTUDIO Google Drive inventory")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "validate-rules"])
    parser.add_argument("--scope", default="all-accessible-drive", choices=["all-accessible-drive", "root", "folder"])
    parser.add_argument("--root-folder-id", default="")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--out-dir", default="out/drive_inventory")
    parser.add_argument("--mode", default="full", choices=["inventory", "duplicates", "classify", "metadata-classification", "full"])
    parser.add_argument("--cache", default="")
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--skip-google-sheets", default="true")
    parser.add_argument("--dry-run", default="true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--include-content-hash", action="store_true")
    parser.add_argument("--include-google-export-hash", action="store_true")
    parser.add_argument("--include-media-hash", action="store_true")
    parser.add_argument("--include-perceptual-image-hash", action="store_true")
    parser.add_argument("--enable-content-inspection", default="true")
    parser.add_argument("--content-inspection-max-files", type=int, default=None)
    parser.add_argument("--content-char-limit", type=int, default=None)
    parser.add_argument("--content-page-limit", type=int, default=None)
    parser.add_argument("--max-download-size-mb", type=int, default=None)
    parser.add_argument("--enable-ocr", default="false")
    parser.add_argument("--enable-excel-content-inspection", default="true")
    parser.add_argument("--store-content-preview", default="false")
    parser.add_argument("--store-sensitive-snippets", default="false")
    parser.add_argument("--content-rules-config", default="")
    parser.add_argument("--safe-mode", default="true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    config = load_inventory_config(args.config)
    config = config.__class__(
        scope=args.scope or config.scope,
        root_folder_id=args.root_folder_id or config.root_folder_id,
        page_size=config.page_size,
        max_download_bytes=config.max_download_bytes,
        skip_google_sheets=as_bool(args.skip_google_sheets),
        include_content_hash=args.include_content_hash or config.include_content_hash,
        include_google_export_hash=args.include_google_export_hash or config.include_google_export_hash,
        include_media_hash=args.include_media_hash or config.include_media_hash,
        include_perceptual_image_hash=args.include_perceptual_image_hash or config.include_perceptual_image_hash,
        enable_content_inspection=as_bool(args.enable_content_inspection),
        content_inspection_max_files=(
            args.content_inspection_max_files
            if args.content_inspection_max_files is not None
            else config.content_inspection_max_files
        ),
        content_char_limit=args.content_char_limit if args.content_char_limit is not None else config.content_char_limit,
        content_page_limit=args.content_page_limit if args.content_page_limit is not None else config.content_page_limit,
        max_download_size_mb=args.max_download_size_mb if args.max_download_size_mb is not None else config.max_download_size_mb,
        enable_ocr=as_bool(args.enable_ocr),
        enable_image_ocr=config.enable_image_ocr,
        enable_pdf_ocr=config.enable_pdf_ocr,
        enable_presentation_ocr=config.enable_presentation_ocr,
        enable_google_cloud_vision=config.enable_google_cloud_vision,
        enable_document_ai=config.enable_document_ai,
        ocr_max_files=config.ocr_max_files,
        ocr_max_pages_per_file=config.ocr_max_pages_per_file,
        ocr_max_file_size_mb=config.ocr_max_file_size_mb,
        ocr_only_for_review_queue=config.ocr_only_for_review_queue,
        ocr_only_for_document_scan_candidates=config.ocr_only_for_document_scan_candidates,
        ocr_allow_sensitive=config.ocr_allow_sensitive,
        ocr_store_text=config.ocr_store_text,
        ocr_store_sensitive_snippets=config.ocr_store_sensitive_snippets,
        allow_sensitive_cloud_ai=config.allow_sensitive_cloud_ai,
        allow_cloud_ai_calls=config.allow_cloud_ai_calls,
        enable_excel_content_inspection=as_bool(args.enable_excel_content_inspection),
        store_content_preview=as_bool(args.store_content_preview),
        store_sensitive_snippets=as_bool(args.store_sensitive_snippets),
        content_rules_config=args.content_rules_config or config.content_rules_config,
        classification_taxonomy_config=config.classification_taxonomy_config,
        path_rules_config=config.path_rules_config,
        filename_rules_config=config.filename_rules_config,
        extension_rules_config=config.extension_rules_config,
        sensitivity_rules_config=config.sensitivity_rules_config,
        media_rules_config=config.media_rules_config,
        cleanup_rules_config=config.cleanup_rules_config,
        classification_use_rule_index=config.classification_use_rule_index,
        classification_strict_full_scan=config.classification_strict_full_scan,
        classification_normalization_cache_size=config.classification_normalization_cache_size,
        classification_slow_rule_ms=config.classification_slow_rule_ms,
        unknown_object_rate_max=config.unknown_object_rate_max,
        unknown_department_rate_max=config.unknown_department_rate_max,
        unknown_document_type_rate_max=config.unknown_document_type_rate_max,
        conflict_rate_max=config.conflict_rate_max,
        sensitive_unknown_rate_max=config.sensitive_unknown_rate_max,
        safe_mode=as_bool(args.safe_mode),
        cache_dir=args.cache or config.cache_dir,
    )
    out_dir = Path(args.out_dir)
    if args.command == "validate-rules":
        report = write_rule_validation_reports(config, out_dir)
        print(json.dumps(report.summary, ensure_ascii=False, indent=2))
        return 1 if report.errors else 0
    if not as_bool(args.dry_run):
        raise RuntimeError("Drive inventory is read-only. --dry-run must remain true for this first-stage contour.")
    if not config.skip_google_sheets:
        raise RuntimeError("Google Sheets must be skipped in the first-stage inventory.")
    if config.store_sensitive_snippets:
        raise RuntimeError("Sensitive snippets must not be stored in the first-stage inventory.")

    run_log = out_dir / "run_log.jsonl"
    service = build_read_only_drive_service()
    client = DriveInventoryClient(service, config=config)
    scanner = DriveInventoryScanner(client=client, config=config)
    result = scanner.scan(
        scope=args.scope,
        mode=args.mode,
        root_folder_id=args.root_folder_id or config.root_folder_id or "",
        max_files=max(0, args.max_files),
        run_log_path=run_log,
    )
    write_reports(result, out_dir)
    summary = {
        "outDir": str(out_dir),
        "totalListed": len(result.items),
        "filesInventoried": len(result.files),
        "folders": len(result.folders),
        "skippedGoogleSheets": len(result.skipped_google_sheets),
        "errors": len(result.errors),
        "dryRun": True,
        "readOnly": True,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
