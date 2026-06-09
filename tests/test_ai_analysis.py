from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from knowledge_ops.ai_analysis.budget_guard import apply_budget_guard
from knowledge_ops.ai_analysis.config import BudgetLimits
from knowledge_ops.ai_analysis.eligibility import classify_eligibility
from knowledge_ops.ai_analysis.estimator import estimate, load_inventory, sample_plan
from knowledge_ops.ai_analysis.models import AIFileRecord, ScenarioEstimate
from knowledge_ops.ai_analysis.pricing import PricingTable, PriceEntry
from knowledge_ops.ai_analysis.report_writer import write_outputs
from knowledge_ops.ai_analysis.safety import CloudAnalysisSafetyError, assert_estimate_mode_safe


class AIAnalysisTest(unittest.TestCase):
    def pricing(self):
        return PricingTable({
            ("vision", "text_detection"): PriceEntry("vision", "text_detection", "image", 1, 1, 2.0),
            ("vision", "label_detection"): PriceEntry("vision", "label_detection", "image", 0, 1, 1.0),
            ("document_ai", "enterprise_document_ocr"): PriceEntry("document_ai", "enterprise_document_ocr", "page", 0, 1000, 1.5),
        })

    def test_cost_calculation_with_free_tier(self):
        table = self.pricing()
        self.assertEqual(table.cost("vision", "text_detection", 1), 0)
        self.assertEqual(table.cost("vision", "text_detection", 3), 4.0)

    def test_google_sheets_skip_and_duplicate_exclusion(self):
        sheet = classify_eligibility(AIFileRecord("s", "s", "/s", "application/vnd.google-apps.spreadsheet", "", is_google_sheet_skipped=True))
        self.assertEqual(sheet.eligibility_status, "SKIPPED_GOOGLE_SHEET")
        duplicate = classify_eligibility(AIFileRecord("d2", "d", "/d", "application/pdf", "pdf", duplicate_kind="exact", canonical_candidate_id="d1"))
        self.assertEqual(duplicate.eligibility_status, "SKIPPED_DUPLICATE")

    def test_sensitivity_requires_approval(self):
        record = classify_eligibility(AIFileRecord("1", "contract.pdf", "/contract.pdf", "application/pdf", "pdf", sensitivity_suggestion="legal_contract"))
        self.assertTrue(record.requires_manual_approval)
        self.assertEqual(record.eligibility_status, "SKIPPED_SENSITIVE_REQUIRES_APPROVAL")

    def test_budget_guard_marks_over_budget(self):
        estimate_obj = apply_budget_guard(
            ScenarioEstimate("deep", total_cost_usd=200, status="OK", service_costs={"vision": 200}),
            BudgetLimits(max_total_cost_usd=100),
        )
        self.assertEqual(estimate_obj.status, "OVER_BUDGET")

    def test_budget_guard_applies_unit_limits(self):
        estimate_obj = apply_budget_guard(
            ScenarioEstimate("deep", total_cost_usd=10, status="OK", service_units={"document_ai": 20}),
            BudgetLimits(max_total_cost_usd=100, max_pages_for_document_ai=10),
        )
        self.assertEqual(estimate_obj.status, "OVER_BUDGET")
        self.assertIn("document_ai units", estimate_obj.reasons[0])

    def test_sample_plan_reproducible(self):
        records = [classify_eligibility(AIFileRecord(str(i), f"{i}.png", f"/{i}.png", "image/png", "png")) for i in range(10)]
        first = [record.file_id for record in sample_plan(records, 4, 7)]
        second = [record.file_id for record in sample_plan(records, 4, 7)]
        self.assertEqual(first, second)

    def test_no_cloud_calls_in_estimate_mode(self):
        assert_estimate_mode_safe("estimate")
        with self.assertRaises(CloudAnalysisSafetyError):
            assert_estimate_mode_safe("analyze-sample")

    def test_load_inventory_and_report_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inventory = tmp_path / "inventory.csv"
            with inventory.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=["file_id", "name", "full_path", "mime_type", "extension", "size", "sensitivity_suggestion"])
                writer.writeheader()
                writer.writerow({"file_id": "1", "name": "scan.png", "full_path": "/scan.png", "mime_type": "image/png", "extension": "png", "size": "100", "sensitivity_suggestion": "unknown"})
            records = load_inventory(inventory)
            self.assertEqual(len(records), 1)
            class Config:
                scenarios = ["metadata_only", "cheap"]
                sample_size = 2
                random_seed = 1
                max_file_size_mb_for_cloud = 200
                budget = BudgetLimits(max_total_cost_usd=100)
            result = estimate(records, self.pricing(), "missing.yml", Config())
            out = tmp_path / "out"
            write_outputs(result, out)
            self.assertTrue((out / "pricing_estimate.xlsx").exists())
            self.assertTrue((out / "cloud_setup_checklist.md").exists())


if __name__ == "__main__":
    unittest.main()
