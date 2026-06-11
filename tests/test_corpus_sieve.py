from __future__ import annotations

import csv
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from knowledge_ops.drive_inventory.__main__ import main
from knowledge_ops.drive_inventory.corpus_sieve import CORPUS_COLUMNS, build_corpus_sieve, load_corpus_sieve_config, run_corpus_sieve


def inventory_row(file_id: str, name: str, **overrides):
    row = {
        "file_id": file_id,
        "name": name,
        "object_kind": "file",
        "mime_type": overrides.get("mime_type", "application/pdf"),
        "extension": overrides.get("extension", name.rsplit(".", 1)[-1].lower() if "." in name else ""),
        "size": str(overrides.get("size", 100)),
        "md5_checksum": overrides.get("md5_checksum", ""),
        "content_hash": overrides.get("content_hash", ""),
        "export_hash": overrides.get("export_hash", ""),
        "created_time": "2026-01-01T00:00:00Z",
        "modified_time": overrides.get("modified_time", "2026-01-01T00:00:00Z"),
        "full_path": overrides.get("full_path", f"/Drive/{name}"),
        "duplicate_group_id": overrides.get("duplicate_group_id", ""),
        "duplicate_kind": overrides.get("duplicate_kind", ""),
        "canonical_candidate_id": overrides.get("canonical_candidate_id", ""),
        "object_suggestion": overrides.get("object_suggestion", "ARTSTUDIO Nevsky"),
        "department_suggestion": overrides.get("department_suggestion", "Finance"),
        "document_type_suggestion": overrides.get("document_type_suggestion", "report"),
        "sensitivity_suggestion": overrides.get("sensitivity_suggestion", "operational"),
        "lifecycle_status": overrides.get("lifecycle_status", "current"),
        "cleanup_category": overrides.get("cleanup_category", "keep_review"),
        "human_review_queue": overrides.get("human_review_queue", "knowledge_base_review"),
    }
    return row


class CorpusSieveTest(unittest.TestCase):
    def test_builds_canonical_corpus_and_suppresses_exact_duplicates(self):
        config = load_corpus_sieve_config("configs/corpus_sieve_rules.yml")
        inventory = [
            inventory_row("canonical", "report final.pdf", md5_checksum="same", size=100, modified_time="2026-01-02T00:00:00Z"),
            inventory_row("duplicate", "report copy.pdf", md5_checksum="same", size=100, modified_time="2026-01-01T00:00:00Z"),
            inventory_row("legal_a", "contract signed.pdf", md5_checksum="legal", size=200, sensitivity_suggestion="legal_contract"),
            inventory_row("legal_b", "contract copy.pdf", md5_checksum="legal", size=200, sensitivity_suggestion="legal_contract"),
            inventory_row("trash", "Thumbs.db", extension="db", mime_type="application/octet-stream", cleanup_category="system_trash_candidate"),
            inventory_row("installer", "setup.exe", extension="exe", mime_type="application/octet-stream"),
            inventory_row("archive", "documents.zip", extension="zip", mime_type="application/zip"),
            inventory_row("empty", "empty.txt", extension="txt", mime_type="text/plain", size=0),
        ]
        result = build_corpus_sieve(inventory, config)
        by_id = {row["file_id"]: row for row in result.rows}

        self.assertEqual(by_id["canonical"]["corpus_status"], "CORPUS_KEEP_CANONICAL")
        self.assertEqual(by_id["duplicate"]["corpus_status"], "CORPUS_SUPPRESS_EXACT_DUPLICATE")
        self.assertEqual(by_id["duplicate"]["safe_for_content_processing"], "false")
        self.assertEqual(by_id["legal_b"]["corpus_status"], "CORPUS_HOLD_LEGAL")
        self.assertEqual(by_id["legal_b"]["safe_for_physical_delete_candidate"], "false")
        self.assertEqual(by_id["trash"]["corpus_status"], "CORPUS_EXCLUDE_SYSTEM_TRASH")
        self.assertEqual(by_id["installer"]["corpus_status"], "CORPUS_EXCLUDE_INSTALLER")
        self.assertEqual(by_id["archive"]["corpus_status"], "CORPUS_HOLD_ARCHIVE_CONTAINER")
        self.assertEqual(by_id["empty"]["corpus_status"], "CORPUS_EXCLUDE_EMPTY")
        self.assertEqual(result.metrics["exact_duplicate_groups"], 2)
        self.assertGreater(result.metrics["estimated_processing_load_reduction_files"], 0)

    def test_writes_stage1_outputs(self):
        rows = [
            inventory_row("a", "a.pdf", md5_checksum="same", size=10),
            inventory_row("b", "b.pdf", md5_checksum="same", size=10),
            inventory_row("trash", ".DS_Store", extension=""),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_path = root / "classification_v3_inventory.csv"
            write_inventory(inventory_path, rows)
            out_dir = root / "stage1"
            result = run_corpus_sieve(inventory_path, "configs/corpus_sieve_rules.yml", out_dir)

            self.assertTrue((out_dir / "corpus_sieve_inventory.csv").exists())
            self.assertTrue((out_dir / "corpus_keep_canonical.csv").exists())
            self.assertTrue((out_dir / "corpus_excluded.csv").exists())
            self.assertTrue((out_dir / "corpus_review_queue.csv").exists())
            self.assertTrue((out_dir / "dedup_exact_canonical_map.csv").exists())
            self.assertTrue((out_dir / "dedup_exact_actions_dry_run.csv").exists())
            self.assertTrue((out_dir / "corpus_sieve_report.md").exists())
            self.assertTrue((out_dir / "corpus_sieve_manifest.jsonl").exists())
            metrics = json.loads((out_dir / "corpus_sieve_metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["total_files_considered"], result.metrics["total_files_considered"])
            actions = read_csv(out_dir / "dedup_exact_actions_dry_run.csv")
            self.assertTrue(all(row["dry_run_only"] == "true" for row in actions))

    def test_cli_corpus_sieve_does_not_require_drive_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_path = root / "classification_v3_inventory.csv"
            write_inventory(
                inventory_path,
                [
                    inventory_row("a", "a.pdf", md5_checksum="same", size=10),
                    inventory_row("b", "b.pdf", md5_checksum="same", size=10),
                ],
            )
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "corpus-sieve",
                        "--inventory",
                        str(inventory_path),
                        "--rules",
                        "configs/corpus_sieve_rules.yml",
                        "--out-dir",
                        str(root / "stage1"),
                        "--mode",
                        "dry-run",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue((root / "stage1" / "corpus_sieve_inventory.csv").exists())


def write_inventory(path: Path, rows):
    columns = sorted({key for row in rows for key in row.keys()} | set(CORPUS_COLUMNS))
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


if __name__ == "__main__":
    unittest.main()
