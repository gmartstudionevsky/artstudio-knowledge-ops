from __future__ import annotations

import unittest
from unittest.mock import patch

from knowledge_ops.drive_inventory.config import InventoryConfig
from knowledge_ops.drive_inventory.content_inspector import (
    ContentInspector,
    ContentRule,
    ContentRuleEngine,
    apply_content_result,
)
from knowledge_ops.drive_inventory.models import SHEETS_MIME, DriveInventoryItem


class FakeDriveClient:
    def __init__(self, data: bytes):
        self.data = data
        self.download_calls = 0

    def download_bytes(self, file_obj, max_bytes):
        self.download_calls += 1
        if len(self.data) > max_bytes:
            raise ValueError("file_too_large")
        return self.data

    def export_text(self, file_obj, max_bytes):
        if len(self.data) > max_bytes:
            raise ValueError("file_too_large")
        return self.data.decode("utf-8")


class ContentInspectionTest(unittest.TestCase):
    def test_rule_engine_matches_keywords_regex_and_sensitivity(self):
        engine = ContentRuleEngine([
            ContentRule(
                rule_id="finance",
                category="finance",
                keywords=("счёт", "оплата"),
                regex_patterns=(r"\b\d{20}\b",),
                weight=3,
                target_fields={"department_suggestion": "финансы", "document_type_suggestion": "счёт"},
                sensitivity_flags=("financial",),
                explanation="finance markers",
            )
        ])
        matches = engine.match("Счёт на оплату 40702810900000000001")
        self.assertEqual(matches[0].rule_id, "finance")
        self.assertIn("financial", matches[0].sensitivity_flags)

    def test_google_sheets_are_never_read(self):
        inspector = ContentInspector(FakeDriveClient(b"secret"), InventoryConfig(), ContentRuleEngine([]))
        item = DriveInventoryItem.from_drive_file({"id": "s", "name": "Sheet", "mimeType": SHEETS_MIME}, "sheet", "")
        result = inspector.inspect(item, {"id": "s", "mimeType": SHEETS_MIME})
        self.assertFalse(result.extracted)
        self.assertEqual(result.status, "skipped_google_sheet")

    def test_content_classification_merges_without_storing_text(self):
        engine = ContentRuleEngine([
            ContentRule(
                rule_id="sop",
                category="sop",
                keywords=("регламент", "порядок действий"),
                target_fields={"document_type_suggestion": "SOP", "process_suggestion": "операционные стандарты"},
                explanation="sop markers",
            )
        ])
        inspector = ContentInspector(FakeDriveClient("Регламент и порядок действий".encode("utf-8")), InventoryConfig(), engine)
        item = DriveInventoryItem("1", "unknown.txt", "unknown", "text/plain", "file", "txt")
        result = inspector.inspect(item, {"id": "1", "name": "unknown.txt", "mimeType": "text/plain", "size": "50"})
        apply_content_result(item, result)
        self.assertTrue(item.content_extracted)
        self.assertEqual(item.document_type_suggestion, "SOP")
        self.assertTrue(item.content_text_hash)
        self.assertFalse(hasattr(item, "content_text"))

    def test_size_limit_becomes_extract_error_not_audit_failure(self):
        config = InventoryConfig(max_download_size_mb=0)
        inspector = ContentInspector(FakeDriveClient(b"too big"), config, ContentRuleEngine([]))
        item = DriveInventoryItem("1", "a.txt", "a", "text/plain", "file", "txt")
        result = inspector.inspect(item, {"id": "1", "name": "a.txt", "mimeType": "text/plain", "size": "100"})
        self.assertEqual(result.status, "extract_error")
        self.assertIn("file_too_large", result.error)

    def test_unsupported_type_is_not_downloaded(self):
        client = FakeDriveClient(b"binary")
        inspector = ContentInspector(client, InventoryConfig(), ContentRuleEngine([]))
        item = DriveInventoryItem("1", "video.mp4", "video", "video/mp4", "file", "mp4")
        result = inspector.inspect(item, {"id": "1", "name": "video.mp4", "mimeType": "video/mp4", "size": "6"})
        self.assertEqual(result.status, "unsupported_type")
        self.assertEqual(client.download_calls, 0)

    def test_ocr_enabled_reports_unavailable_without_failing(self):
        client = FakeDriveClient(b"not really an image")
        inspector = ContentInspector(client, InventoryConfig(enable_ocr=True), ContentRuleEngine([]))
        item = DriveInventoryItem("1", "scan.png", "scan", "image/png", "file", "png")
        with patch("knowledge_ops.drive_inventory.content_inspector.shutil.which", return_value=None):
            result = inspector.inspect(item, {"id": "1", "name": "scan.png", "mimeType": "image/png", "size": "19"})
        self.assertEqual(result.status, "ocr_unavailable")
        self.assertEqual(client.download_calls, 1)


if __name__ == "__main__":
    unittest.main()
