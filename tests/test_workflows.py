from __future__ import annotations

import unittest
from pathlib import Path


class DriveInventoryWorkflowTest(unittest.TestCase):
    def test_metadata_classification_respects_max_files_input(self):
        workflow = Path(".github/workflows/drive-inventory.yml").read_text(encoding="utf-8")
        marker = 'name: "02 metadata classification only"'
        start = workflow.index(marker)
        end = workflow.index("  corpus-sieve:", start)
        job = workflow[start:end]

        self.assertIn('MAX_FILES="${{ github.event.inputs.max_files }}"', job)
        self.assertIn('--max-files "$MAX_FILES"', job)
        self.assertIn('--max-runtime-minutes "${{ github.event.inputs.metadata_max_runtime_minutes }}"', job)
        self.assertNotIn("--max-files 0", job)


if __name__ == "__main__":
    unittest.main()
