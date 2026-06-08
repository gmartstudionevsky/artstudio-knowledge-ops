from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AIFileRecord:
    file_id: str
    name: str
    full_path: str
    mime_type: str
    extension: str
    size: int = 0
    object_suggestion: str = ""
    department_suggestion: str = ""
    document_type_suggestion: str = ""
    sensitivity_suggestion: str = ""
    duplicate_group_id: str = ""
    duplicate_kind: str = ""
    canonical_candidate_id: str = ""
    is_google_sheet_skipped: bool = False
    content_extracted_locally: bool = False
    media_metadata_available: bool = False
    page_count_estimated: int = 0
    page_count_exact: int = 0
    image_count_estimated: int = 0
    video_duration_seconds: int = 0
    audio_duration_seconds: int = 0
    eligible_services: List[str] = field(default_factory=list)
    recommended_service: str = ""
    recommended_features: List[str] = field(default_factory=list)
    cloud_analysis_risk_level: str = "low"
    requires_manual_approval: bool = False
    budget_group: str = "standard"
    estimated_units_by_service: Dict[str, float] = field(default_factory=dict)
    estimated_cost_by_service: Dict[str, float] = field(default_factory=dict)
    scenario_inclusion_flags: Dict[str, bool] = field(default_factory=dict)
    eligibility_status: str = "NOT_ELIGIBLE"
    reason: str = ""


@dataclass
class ScenarioEstimate:
    scenario: str
    total_cost_usd: float
    status: str
    reasons: List[str] = field(default_factory=list)
    service_costs: Dict[str, float] = field(default_factory=dict)
    service_units: Dict[str, float] = field(default_factory=dict)


AI_READINESS_COLUMNS = [
    "file_id", "name", "full_path", "mime_type", "extension", "size", "object_suggestion",
    "department_suggestion", "document_type_suggestion", "sensitivity_suggestion", "duplicate_group_id",
    "is_google_sheet_skipped", "content_extracted_locally", "media_metadata_available", "page_count_estimated",
    "page_count_exact", "image_count_estimated", "video_duration_seconds", "audio_duration_seconds",
    "eligible_services", "recommended_service", "recommended_features", "cloud_analysis_risk_level",
    "requires_manual_approval", "budget_group", "estimated_units_by_service", "estimated_cost_by_service",
    "scenario_inclusion_flags", "eligibility_status", "reason",
]

AI_PLAN_COLUMNS = [
    "file_id", "full_path", "mime_type", "size", "local_classification", "sensitivity", "duplicate_status",
    "recommended_cloud_service", "recommended_features", "scenario_cheap", "scenario_balanced", "scenario_deep",
    "estimated_units", "estimated_cost_usd", "risk_level", "approval_required", "approval_reason",
    "final_decision", "approved_by", "approved_at", "execution_status",
]
