from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List, Optional

from knowledge_ops.drive_inventory.auth import build_read_only_drive_service
from knowledge_ops.drive_inventory.config import as_bool, load_inventory_config
from knowledge_ops.drive_inventory.drive_client import DriveInventoryClient
from knowledge_ops.drive_inventory.report_writer import write_reports
from knowledge_ops.drive_inventory.scanner import DriveInventoryScanner


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only ARTSTUDIO Google Drive inventory")
    parser.add_argument("--scope", default="all-accessible-drive", choices=["all-accessible-drive", "root", "folder"])
    parser.add_argument("--root-folder-id", default="")
    parser.add_argument("--config", default="config/drive-inventory.yml")
    parser.add_argument("--out-dir", default="out/drive_inventory")
    parser.add_argument("--mode", default="full", choices=["inventory", "duplicates", "classify", "full"])
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
        safe_mode=as_bool(args.safe_mode),
        cache_dir=args.cache or config.cache_dir,
    )
    if not as_bool(args.dry_run):
        raise RuntimeError("Drive inventory is read-only. --dry-run must remain true for this first-stage contour.")
    if not config.skip_google_sheets:
        raise RuntimeError("Google Sheets must be skipped in the first-stage inventory.")

    out_dir = Path(args.out_dir)
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
