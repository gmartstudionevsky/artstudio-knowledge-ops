from __future__ import annotations

import argparse
import json
from pathlib import Path

from knowledge_ops.ai_analysis.config import load_analysis_config
from knowledge_ops.ai_analysis.estimator import estimate, load_inventory, write_run_log
from knowledge_ops.ai_analysis.pricing import PricingTable
from knowledge_ops.ai_analysis.report_writer import write_outputs
from knowledge_ops.ai_analysis.safety import assert_estimate_mode_safe


def main() -> int:
    parser = argparse.ArgumentParser(description="AI analysis preparation and pricing estimator")
    parser.add_argument("--inventory", default="out/drive_inventory/inventory.csv")
    parser.add_argument("--media-inventory", default="")
    parser.add_argument("--content-inspection", default="out/drive_inventory/content_inspection.csv")
    parser.add_argument("--out-dir", default="out/ai_analysis_estimate")
    parser.add_argument("--mode", default="estimate", choices=["estimate", "sample-plan", "validate-config", "analyze-sample"])
    parser.add_argument("--pricing-config", default="configs/ai_analysis_pricing.yml")
    parser.add_argument("--routing-config", default="configs/ai_analysis_routing.yml")
    parser.add_argument("--dry-run", default="true")
    parser.add_argument("--scenario", default="")
    parser.add_argument("--max-total-cost-usd", type=float, default=None)
    args = parser.parse_args()

    if str(args.dry_run).lower() != "true":
        raise RuntimeError("AI analysis estimator is dry-run only by default.")
    assert_estimate_mode_safe(args.mode)
    config = load_analysis_config(args.routing_config)
    if args.max_total_cost_usd is not None:
        config.budget.max_total_cost_usd = args.max_total_cost_usd
    if args.scenario:
        config.scenarios = [args.scenario]
    pricing = PricingTable.from_file(args.pricing_config)
    if args.mode == "validate-config":
        summary = {
            "pricing_entries": len(pricing.entries),
            "scenarios": config.scenarios,
            "dry_run": True,
            "cloud_calls": False,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    records = load_inventory(args.inventory, args.content_inspection)
    result = estimate(records, pricing, args.routing_config, config)
    write_outputs(result, args.out_dir)
    write_run_log(Path(args.out_dir) / "run_log.jsonl", {"event": "estimate_complete", "records": len(records)})
    summary = {
        "records": len(records),
        "outDir": args.out_dir,
        "mode": args.mode,
        "dryRun": True,
        "cloudCalls": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
