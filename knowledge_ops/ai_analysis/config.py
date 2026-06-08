from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass
class BudgetLimits:
    max_total_cost_usd: float = 100.0
    max_cost_per_service_usd: Dict[str, float] = field(default_factory=dict)
    max_images_for_cloud_analysis: int = 1000
    max_pages_for_document_ai: int = 5000
    max_video_minutes: int = 120
    max_audio_minutes: int = 120
    max_sensitive_files: int = 0
    require_approval_for_sensitive: bool = True
    require_approval_above_cost_usd: float = 25.0
    require_approval_for_document_ai_form_parser: bool = True
    require_approval_for_face_detection: bool = True
    require_approval_for_speech_to_text: bool = True
    require_approval_for_video_intelligence: bool = True


@dataclass
class AIAnalysisConfig:
    scenarios: List[str] = field(default_factory=lambda: ["metadata_only", "cheap", "balanced", "deep"])
    budget: BudgetLimits = field(default_factory=BudgetLimits)
    sample_size: int = 50
    random_seed: int = 42
    max_file_size_mb_for_cloud: int = 200


def load_yaml(path: str | Path) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_analysis_config(path: str | Path) -> AIAnalysisConfig:
    data = load_yaml(path).get("ai_analysis", load_yaml(path))
    budget_data = data.get("budget_limits", {})
    budget = BudgetLimits(
        max_total_cost_usd=float(budget_data.get("max_total_cost_usd", 100.0)),
        max_cost_per_service_usd=budget_data.get("max_cost_per_service_usd", {}) or {},
        max_images_for_cloud_analysis=int(budget_data.get("max_images_for_cloud_analysis", 1000)),
        max_pages_for_document_ai=int(budget_data.get("max_pages_for_document_ai", 5000)),
        max_video_minutes=int(budget_data.get("max_video_minutes", 120)),
        max_audio_minutes=int(budget_data.get("max_audio_minutes", 120)),
        max_sensitive_files=int(budget_data.get("max_sensitive_files", 0)),
        require_approval_for_sensitive=as_bool(budget_data.get("require_approval_for_sensitive", True)),
        require_approval_above_cost_usd=float(budget_data.get("require_approval_above_cost_usd", 25.0)),
        require_approval_for_document_ai_form_parser=as_bool(budget_data.get("require_approval_for_document_ai_form_parser", True)),
        require_approval_for_face_detection=as_bool(budget_data.get("require_approval_for_face_detection", True)),
        require_approval_for_speech_to_text=as_bool(budget_data.get("require_approval_for_speech_to_text", True)),
        require_approval_for_video_intelligence=as_bool(budget_data.get("require_approval_for_video_intelligence", True)),
    )
    return AIAnalysisConfig(
        scenarios=data.get("scenarios", ["metadata_only", "cheap", "balanced", "deep"]),
        budget=budget,
        sample_size=int(data.get("sample_size", 50)),
        random_seed=int(data.get("random_seed", 42)),
        max_file_size_mb_for_cloud=int(data.get("max_file_size_mb_for_cloud", 200)),
    )


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
