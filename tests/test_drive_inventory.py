from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

import yaml

from knowledge_ops.drive_inventory.classifier import MetadataClassifier, classify_item, validate_rule_configs
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
        self.assertEqual(item.department_suggestion, "Owner Relations / отдел по работе с собственниками")
        self.assertEqual(item.document_family_suggestion, "contract")
        self.assertEqual(item.sensitivity_suggestion, "owner_contract")

    def assert_classifies(self, path, name, expected):
        extension = split_extension(name, "application/pdf")[1] or "pdf"
        mime_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }.get(extension, "application/pdf")
        item = DriveInventoryItem(
            file_id="x",
            name=name,
            normalized_name=normalize_name(name),
            mime_type=mime_type,
            object_kind="file",
            extension=extension,
            full_path=path,
        )
        classify_item(item)
        for field, value in expected.items():
            self.assertEqual(getattr(item, field), value, f"{field} for {path} / {name}")
        return item

    def test_v31_real_drive_pattern_fixtures(self):
        fixture_path = Path("tests/fixtures/classification_v3_real_patterns.yml")
        data = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
        for case in data["cases"]:
            item = self.assert_classifies(case["path"], case["name"], case.get("expected", {}))
            for field, value in case.get("not_expected", {}).items():
                self.assertNotEqual(getattr(item, field), value, f"{field} for {case['path']}")
            if item.source_origin == "auto_structured_artstudio_base":
                self.assertIn(
                    "ARTSTUDIO base path ignored as business context because it was auto-structured before analysis.",
                    item.classification_reason,
                )
        for case in data["negative_cases"]:
            item = self.assert_classifies(case["path"], case["name"], {})
            for field, value in case.get("not_expected", {}).items():
                self.assertNotEqual(getattr(item, field), value, f"{field} for {case['path']}")

    def test_object_detection_v2(self):
        self.assert_classifies("/Public - копия/Отдел по работе с собственниками/2Советская", "file.pdf", {"object_suggestion": "ARTSTUDIO Nevsky"})
        self.assert_classifies("/Передача Заозерная/Договоры", "file.pdf", {"object_suggestion": "ARTSTUDIO Moskovsky"})
        self.assert_classifies("/М103 (все доки с паблика)", "file.pdf", {"object_suggestion": "ARTSTUDIO M103"})
        self.assert_classifies("/ЭР-БИ-АЙ ПМ/Legal Files", "file.pdf", {"object_suggestion": "RBI PM / УК"})

    def test_department_detection_v2(self):
        cases = [
            ("/Отдел по работе с собственниками", "реестр.pdf", "Owner Relations / отдел по работе с собственниками"),
            ("/Front Office", "check-in.pdf", "СПиР / Front Office / Reception"),
            ("/Housekeeping", "чеклист.pdf", "Housekeeping / ХСК / HSK / HSKP"),
            ("/ИТС", "ППР.pdf", "Engineering / ИТС / техническая служба"),
            ("/Коммерческий отдел", "pricing.pdf", "Revenue"),
            ("/Отдел маркетинга/Фото SMM", "photo.jpg", "Content / Photo / Video"),
            ("/Отдел бронирования/OTA", "tl.pdf", "OTA / электронные каналы"),
            ("/Отдел продаж", "pipeline.pdf", "Sales / отдел продаж"),
            ("/Отдел кадров шаблоны", "табели.xlsx", "HR / кадры"),
        ]
        for path, name, department in cases:
            self.assert_classifies(path, name, {"department_suggestion": department})

    def test_document_type_detection_v2(self):
        cases = [
            ("Договор ТО.pdf", "technical_maintenance_contract"),
            ("Агентские договоры.pdf", "agency_contract"),
            ("ДКП.pdf", "purchase_sale_contract"),
            ("ДДУ.pdf", "DDU"),
            ("АПП.pdf", "acceptance_transfer_act"),
            ("Выписки ЕГРН.pdf", "owner_EGRN_extract"),
            ("УПД.pdf", "UPD"),
            ("квитанции на аванс.pdf", "invoice"),
            ("табели.xlsx", "timesheet"),
            ("SOP check-in.pdf", "checkin_sop"),
            ("Фото SMM.jpg", "SMM_photo"),
            ("КП и счета.pdf", "invoice"),
        ]
        for name, document_type in cases:
            self.assert_classifies("/ARTSTUDIO Nevsky/Рабочая папка", name, {"document_type_suggestion": document_type})

    def test_system_trash_detection_v2(self):
        for name in ["Thumbs.db", ".DS_Store", "desktop.ini", "Temp.tmp", "Diagnostics.log", "shortcut.lnk", "draft.tmp", "old.wbk"]:
            item = self.assert_classifies("/Temp/Diagnostics", name, {"cleanup_category": "system_trash_candidate"})
            self.assertEqual(item.classification_status, "CLASSIFIED_SYSTEM_TRASH")

    def test_v3_extracts_entities_review_queue_and_cloud_approval(self):
        item = self.assert_classifies(
            "/ARTSTUDIO Moskovsky/Выписки ЕГРН/апартамент 120",
            "Договор № АМ-120 ИНН 7812345678 БИК 044525225 78:12:1234567:10 scan.pdf",
            {
                "object_suggestion": "ARTSTUDIO Moskovsky",
                "human_review_queue": "cloud_ai_approval_review",
            },
        )
        self.assertEqual(item.contract_number_detected, "АМ-120")
        self.assertEqual(item.INN_detected, "7812345678")
        self.assertEqual(item.BIK_detected, "044525225")
        self.assertEqual(item.cadastral_number_detected, "78:12:1234567:10")
        self.assertIn("bank_details", item.sensitivity_flags)
        self.assertTrue(item.ocr_candidate)
        self.assertEqual(item.cloud_analysis_recommended_service, "Document AI")
        self.assertTrue(item.cloud_analysis_approval_required)

    def test_v3_system_files_get_specific_type(self):
        item = self.assert_classifies("/Temp", "Thumbs.db", {"document_type_suggestion": "thumbs_db"})
        self.assertEqual(item.human_review_queue, "system_trash_review")

    def test_v3_signature_seal_is_do_not_touch(self):
        item = self.assert_classifies("/Legal Files", "Подпись&Печать.png", {"sensitivity_suggestion": "signature_seal_sensitive"})
        self.assertEqual(item.action_recommendation, "DO_NOT_TOUCH")
        self.assertTrue(item.cloud_analysis_approval_required)

    def test_v3_utility_rule_does_not_steal_regular_receipt(self):
        item = self.assert_classifies("/ARTSTUDIO Nevsky/Рабочая папка", "квитанции на аванс.pdf", {"document_type_suggestion": "invoice"})
        self.assertNotEqual(item.document_type_suggestion, "utility_receipt_package")

    def test_indexed_engine_matches_full_scan_for_v2_examples(self):
        indexed_config = InventoryConfig(classification_use_rule_index=True, classification_strict_full_scan=False)
        full_config = InventoryConfig(classification_use_rule_index=False, classification_strict_full_scan=True)
        indexed = MetadataClassifier(indexed_config)
        full = MetadataClassifier(full_config)
        samples = [
            ("/Public - копия/Отдел по работе с собственниками/2Советская", "file.pdf"),
            ("/Передача Заозерная/Договоры", "ДКП.pdf"),
            ("/М103 (все доки с паблика)", "ДДУ.pdf"),
            ("/Отдел маркетинга/Фото SMM", "photo.jpg"),
            ("/Temp/Diagnostics", "Thumbs.db"),
        ]
        fields = [
            "object_suggestion",
            "department_suggestion",
            "document_family_suggestion",
            "document_type_suggestion",
            "sensitivity_suggestion",
            "cleanup_category",
            "classification_status",
        ]
        for path, name in samples:
            left = DriveInventoryItem("i", name, normalize_name(name), "application/pdf", "file", split_extension(name, "application/pdf")[1] or "pdf", full_path=path)
            right = DriveInventoryItem("f", name, normalize_name(name), "application/pdf", "file", split_extension(name, "application/pdf")[1] or "pdf", full_path=path)
            indexed.classify(left)
            full.classify(right)
            for field in fields:
                self.assertEqual(getattr(left, field), getattr(right, field), f"{field} for {path}/{name}")

    def test_invalid_regex_is_reported_by_rule_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            rule_path = Path(tmp) / "bad.yml"
            rule_path.write_text(
                "rules:\n"
                "  - rule_id: bad_regex\n"
                "    regex_patterns: ['([']\n"
                "    target_fields: {document_type_suggestion: test}\n"
                "    weight: 1\n",
                encoding="utf-8",
            )
            config = InventoryConfig(
                path_rules_config=str(rule_path),
                filename_rules_config=str(rule_path),
                extension_rules_config=str(rule_path),
                sensitivity_rules_config=str(rule_path),
                media_rules_config=str(rule_path),
                cleanup_rules_config=str(rule_path),
            )
            report = validate_rule_configs(config)
            self.assertTrue(report.errors)
            self.assertTrue(any("invalid regex" in row["message"] for row in report.errors))


class DriveInventoryDuplicateTest(unittest.TestCase):
    def test_exact_duplicates_by_md5_and_size(self):
        first = DriveInventoryItem("1", "a.pdf", "a", "application/pdf", "file", "pdf", 10, "same")
        second = DriveInventoryItem("2", "copy a.pdf", "copy a", "application/pdf", "file", "pdf", 10, "same")
        groups = mark_exact_duplicates([first, second])
        self.assertEqual(len(groups), 1)
        self.assertEqual(first.duplicate_kind, "exact")
        self.assertTrue(first.canonical_candidate_id)

    def test_sensitive_exact_duplicates_go_to_sensitive_review(self):
        first = DriveInventoryItem("1", "contract.pdf", "contract", "application/pdf", "file", "pdf", 10, "same")
        second = DriveInventoryItem("2", "copy contract.pdf", "copy contract", "application/pdf", "file", "pdf", 10, "same")
        first.sensitivity_suggestion = "owner_contract"
        second.sensitivity_suggestion = "owner_contract"
        mark_exact_duplicates([first, second])
        duplicate = second if second.file_id != second.canonical_candidate_id else first
        self.assertEqual(duplicate.cleanup_category, "sensitive_duplicate_review")
        self.assertEqual(duplicate.human_review_queue, "sensitive_data_review")
        self.assertEqual(duplicate.action_recommendation, "SENSITIVE_REVIEW_REQUIRED")

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
            self.assertTrue((Path(tmp) / "classification_performance.json").exists())
            self.assertTrue((Path(tmp) / "rule_performance.csv").exists())
            self.assertTrue((Path(tmp) / "zero_hit_rules.csv").exists())
            self.assertTrue((Path(tmp) / "slow_rules.csv").exists())
            self.assertTrue((Path(tmp) / "classification_quality_summary.csv").exists())
            self.assertTrue((Path(tmp) / "classification_v3_inventory.csv").exists())
            self.assertTrue((Path(tmp) / "classification_v3_review.csv").exists())
            self.assertTrue((Path(tmp) / "classification_v3_ocr_candidates.csv").exists())
            self.assertTrue((Path(tmp) / "classification_v3_cloud_ai_candidates.csv").exists())
            self.assertTrue((Path(tmp) / "classification_v3_report.md").exists())
            self.assertTrue((Path(tmp) / "human_review_guide.md").exists())


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
