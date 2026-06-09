from __future__ import annotations

from knowledge_ops.ai_analysis.config import BudgetLimits
from knowledge_ops.ai_analysis.models import ScenarioEstimate


def apply_budget_guard(estimate: ScenarioEstimate, budget: BudgetLimits, sensitive_files: int = 0) -> ScenarioEstimate:
    if estimate.total_cost_usd > budget.max_total_cost_usd:
        estimate.status = "OVER_BUDGET"
        estimate.reasons.append(f"Total cost {estimate.total_cost_usd:.2f} exceeds max_total_cost_usd {budget.max_total_cost_usd:.2f}.")
    elif estimate.total_cost_usd > budget.require_approval_above_cost_usd:
        estimate.status = "APPROVAL_REQUIRED"
        estimate.reasons.append(
            f"Total cost {estimate.total_cost_usd:.2f} exceeds approval threshold {budget.require_approval_above_cost_usd:.2f}."
        )
    for service, cost in estimate.service_costs.items():
        limit = float(budget.max_cost_per_service_usd.get(service, budget.max_total_cost_usd))
        if cost > limit:
            estimate.status = "OVER_BUDGET"
            estimate.reasons.append(f"{service} cost {cost:.2f} exceeds service limit {limit:.2f}.")
    unit_limits = {
        "vision": (budget.max_images_for_cloud_analysis, "image/page units"),
        "document_ai": (budget.max_pages_for_document_ai, "pages"),
        "video_intelligence": (budget.max_video_minutes, "video minutes"),
        "speech_to_text": (budget.max_audio_minutes, "audio minutes"),
    }
    for service, (limit, label) in unit_limits.items():
        units = float(estimate.service_units.get(service, 0.0))
        if limit and units > limit:
            estimate.status = "OVER_BUDGET"
            estimate.reasons.append(f"{service} units {units:.2f} exceed limit {limit} {label}.")
    if sensitive_files > budget.max_sensitive_files and budget.require_approval_for_sensitive:
        estimate.reasons.append("Sensitive files require manual approval and are not auto-approved for Cloud AI.")
    return estimate
