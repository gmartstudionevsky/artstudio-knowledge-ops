from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from knowledge_ops.drive_inventory.classifier import classify_item
from knowledge_ops.drive_inventory.duplicate_detector import mark_exact_duplicates, mark_version_candidates
from knowledge_ops.drive_inventory.models import SHEETS_MIME, DriveInventoryItem
from knowledge_ops.drive_inventory.normalizer import normalize_name, split_extension, strip_version_markers
from knowledge_ops.drive_inventory.report_writer import build_migration_plan
from knowledge_ops.drive_inventory.report_writer import write_reports
from knowledge_ops.drive_inventory.safety import ReadOnlySafetyError, assert_read_only_operation, assert_safe_recommendation
from knowledge_ops.drive_inventory.config import InventoryConfig, load_inventory_config
from knowledge_ops.drive_inventory.__main__ import DEFAULT_CONFIG_PATH
from knowledge_ops.drive_inventory.scanner import DriveInventoryScanner
from knowledge_ops.drive_inventory.scanner import InventoryResult


class DriveInventoryNormalizerTest(unittest.TestCase):
    def test_normalize_name(self):
        self.assertEqual(normalize_name("  Договор__ФИНАЛ  "), "договор финал")

    def test_split_extension(self):
        base, ext = split_extension("report.final.pdf", "application/pdf")
        self.assertEqual(base, "report.final")
        self.assertEqual(ext, "pdf")

    def test_version_markers_are_stripped(self):
        self.assertEqual(strip_version_markers("Договор собственника копия v2 (1).pdf"), "договор собственника .pdf")


class DriveInventoryPolicyTest(unittest.TestCase):
    def test_google_sheet_is_skipped_item(self):
        item = DriveInventoryItem.from_drive_file(
            {"id": "sheet1", "name": "Finance", "mimeType": SHEETS_MIME},
            normalized_name="finance",
            extension="",
        )
        self.assertTrue(item.is_google_sheet_skipped)
        self.assertEqual(item.object_kind, "skipped_google_sheet")
        self.assertEqual(item.action_recommendation, "SKIPPED_GOOGLE_SHEET")

    def test_destructive_drive_operations_are_forbidden(self):
        with self.assertRaises(ReadOnlySafetyError):
            assert_read_only_operation("files.update")

    def test_delete_recommendation_is_forbidden(self):
        with self.assertRaises(ReadOnlySafetyError):
            assert_safe_recommendation("DELETE")

    def test_default_config_path_matches_documented_config(self):
        config = load_inventory_config("configs/drive_inventory.yml")
        self.assertTrue(config.skip_google_sheets)
        self.assertEqual(config.content_rules_config, "configs/drive_content_rules.yml")

    def test_cli_default_config_path_is_documented_path(self):
        self.assertEqual(DEFAULT_CONFIG_PATH, "configs/drive_inventory.yml")


class DriveInventoryClassifierTest(unittest.TestCase):
    def test_classifies_object_department_type_and_sensitivity(self):
        item = DriveInventoryItem(
            file_id="1",
            name="ARTSTUDIO Nevsky договор собственника 2025.pdf",
            normalized_name="artstudio nevsky договор собственника 2025",
            mime_type="application/pdf",
            object_kind="file",
            extension="pdf",
            full_path="/ARTSTUDIO Nevsky/Собственники/Договоры/ARTSTUDIO Nevsky договор собственника 2025.pdf",
        )
        classify_item(item)
        self.assertEqual(item.object_suggestion, "ARTSTUDIO Nevsky")
        self.assertEqual(item.department_suggestion, "собственники / owner relations")
        self.assertEqual(item.document_type_suggestion, "договор")
        self.assertEqual(item.sensitivity_suggestion, "owner_data")


class DriveInventoryDuplicateTest(unittest.TestCase):
    def test_exact_duplicates_by_md5_and_size(self):
        first = DriveInventoryItem("1", "a.pdf", "a", "application/pdf", "file", "pdf", 10, "same")
        second = DriveInventoryItem("2", "copy a.pdf", "copy a", "application/pdf", "file", "pdf", 10, "same")
        groups = mark_exact_duplicates([first, second])
        self.assertEqual(len(groups), 1)
        self.assertEqual(first.duplicate_kind, "exact")
        self.assertTrue(first.canonical_candidate_id)

    def test_version_candidates_by_normalized_name(self):
        first = DriveInventoryItem("1", "Регламент СПиР v1.docx", "регламент спир v1", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "file", "docx")
        second = DriveInventoryItem("2", "Регламент СПиР финал.docx", "регламент спир финал", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "file", "docx")
        groups = mark_version_candidates([first, second])
        self.assertEqual(len(groups), 1)
        self.assertEqual(first.duplicate_kind, "version_candidate")


class DriveInventoryMigrationPlanTest(unittest.TestCase):
    def test_builds_migration_decision_plan_without_execution(self):
        item = DriveInventoryItem(
            file_id="1",
            name="SOP check-in.pdf",
            normalized_name="sop check in",
            mime_type="application/pdf",
            object_kind="file",
            extension="pdf",
            full_path="/Ops/SOP check-in.pdf",
        )
        classify_item(item)
        rows = build_migration_plan([item])
        self.assertEqual(rows[0]["execution_status"], "not_planned")
        self.assertIn("SOP", rows[0]["future_target_area"])

    def test_reports_include_all_objects_and_access_coverage(self):
        file_item = DriveInventoryItem("1", "SOP.pdf", "sop", "application/pdf", "file", "pdf")
        sheet_item = DriveInventoryItem.from_drive_file(
            {"id": "2", "name": "Finance", "mimeType": SHEETS_MIME},
            normalized_name="finance",
            extension="",
        )
        result = InventoryResult(items=[file_item, sheet_item], skipped_google_sheets=[sheet_item])
        with tempfile.TemporaryDirectory() as tmp:
            write_reports(result, Path(tmp))
            self.assertTrue((Path(tmp) / "all_objects.csv").exists())
            self.assertTrue((Path(tmp) / "access_coverage.csv").exists())


class FakeInventoryClient:
    def iter_all_accessible(self, max_files=0):
        return iter([
            {"id": "1", "name": "one.txt", "mimeType": "text/plain", "size": "3"},
            {"id": "2", "name": "two.txt", "mimeType": "text/plain", "size": "3"},
        ])

    def download_bytes(self, file_obj, max_bytes):
        return b"SOP"

    def export_text(self, file_obj, max_bytes):
        return "SOP"


class DriveInventoryContentLimitTest(unittest.TestCase):
    def test_content_inspection_limit_marks_remaining_files(self):
        scanner = DriveInventoryScanner(FakeInventoryClient(), InventoryConfig(content_inspection_max_files=1))
        result = scanner.scan(scope="all-accessible-drive", mode="full")
        statuses = [item.content_extract_status for item in result.items]
        self.assertIn("skipped_content_inspection_limit", statuses)


if __name__ == "__main__":
    unittest.main()
