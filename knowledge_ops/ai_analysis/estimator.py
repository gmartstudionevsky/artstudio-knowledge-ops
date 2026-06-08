from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Dict, List

from knowledge_ops.ai_analysis.budget_guard import apply_budget_guard
from knowledge_ops.ai_analysis.config import AIAnalysisConfig
from knowledge_ops.ai_analysis.eligibility import classify_eligibility
from knowledge_ops.ai_analysis.models import AIFileRecord, ScenarioEstimate
from knowledge_ops.ai_analysis.pricing import PricingTable
from knowledge_ops.ai_analysis.routing import load_scenario_features


def load_inventory(path: str | Path, content_path: str | Path = "") -> List[AIFileRecord]:
    content_by_id = load_content_flags(content_path)
    if not Path(path).exists():
        return []
    records: List[AIFileRecord] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            file_id = row.get("file_id", "")
            content = content_by_id.get(file_id, {})
            records.append(
                AIFileRecord(
                    file_id=file_id,
                    name=row.get("name", ""),
                    full_path=row.get("full_path", ""),
                    mime_type=row.get("mime_type", ""),
                    extension=row.get("extension", ""),
                    size=int(float(row.get("size") or 0)),
                    object_suggestion=row.get("object_suggestion", ""),
                    department_suggestion=row.get("department_suggestion", ""),
                    document_type_suggestion=row.get("document_type_suggestion", ""),
                    sensitivity_suggestion=row.get("sensitivity_suggestion", ""),
                    duplicate_group_id=row.get("duplicate_group_id", ""),
                    duplicate_kind=row.get("duplicate_kind", ""),
                    canonical_candidate_id=row.get("canonical_candidate_id", ""),
                    is_google_sheet_skipped=str(row.get("is_google_sheet_skipped", "")).lower() == "true",
                    content_extracted_locally=str(content.get("content_extracted", row.get("content_extracted", ""))).lower() == "true",
                    page_count_exact=int(float(row.get("page_count_exact") or 0)) if row.get("page_count_exact") else 0,
                )
            )
    return records


def load_content_flags(path: str | Path) -> Dict[str, Dict[str, str]]:
    if not path or not Path(path).exists():
        return {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        return {row.get("file_id", ""): row for row in csv.DictReader(fh)}


def estimate(records: List[AIFileRecord], pricing: PricingTable, routing_config: str, config: AIAnalysisConfig) -> Dict[str, object]:
    scenario_features = load_scenario_features(routing_config)
    for record in records:
        classify_eligibility(record, max_file_size_mb=config.max_file_size_mb_for_cloud)
        estimate_record_units(record, pricing, scenario_features)
    scenarios = [estimate_scenario(name, records, pricing, scenario_features, config) for name in config.scenarios]
    return {
        "records": records,
        "scenarios": scenarios,
        "sample_plan": sample_plan(records, config.sample_size, config.random_seed),
    }


def estimate_record_units(record: AIFileRecord, pricing: PricingTable, scenario_features: Dict[str, Dict[str, List[str]]]) -> None:
    service_units: Dict[str, float] = {}
    service_costs: Dict[str, float] = {}
    features = record.recommended_features or []
    for service in record.eligible_services:
        units = units_for(record, service)
        service_units[service] = units
        feature_cost = 0.0
        for feature in features:
            feature_cost += pricing.cost(service, feature, units)
        service_costs[service] = feature_cost
    record.estimated_units_by_service = service_units
    record.estimated_cost_by_service = service_costs
    for scenario in ["metadata_only", "cheap", "balanced", "deep"]:
        record.scenario_inclusion_flags[scenario] = scenario_includes_record(scenario, record, scenario_features)


def estimate_scenario(
    scenario: str,
    records: List[AIFileRecord],
    pricing: PricingTable,
    scenario_features: Dict[str, Dict[str, List[str]]],
    config: AIAnalysisConfig,
) -> ScenarioEstimate:
    if scenario == "metadata_only":
        return ScenarioEstimate(scenario=scenario, total_cost_usd=0.0, status="OK")
    service_units: Dict[str, float] = {}
    service_costs: Dict[str, float] = {}
    sensitive = 0
    for record in records:
        if not scenario_includes_record(scenario, record, scenario_features):
            continue
        if record.requires_manual_approval:
            sensitive += 1
            continue
        for service in record.eligible_services:
            units = units_for(record, service)
            service_units[service] = service_units.get(service, 0.0) + units
            for feature in scenario_service_features(scenario, service, record, scenario_features):
                service_costs[service] = service_costs.get(service, 0.0) + pricing.cost(service, feature, units)
    estimate_obj = ScenarioEstimate(
        scenario=scenario,
        total_cost_usd=sum(service_costs.values()),
        status="OK",
        service_costs=service_costs,
        service_units=service_units,
    )
    return apply_budget_guard(estimate_obj, config.budget, sensitive_files=sensitive)


def scenario_includes_record(scenario: str, record: AIFileRecord, scenario_features: Dict[str, Dict[str, List[str]]]) -> bool:
    if scenario == "metadata_only":
        return False
    if record.eligibility_status not in {"CLOUD_RECOMMENDED", "SKIPPED_SENSITIVE_REQUIRES_APPROVAL"}:
        return False
    if scenario == "cheap":
        if record.content_extracted_locally:
            return False
        return record.recommended_service == "vision" or (record.recommended_service == "document_ai" and record.page_count_estimated <= 20)
    if scenario == "balanced":
        if record.recommended_service == "video_intelligence":
            return record.video_duration_seconds <= 10 * 60
        return record.recommended_service in {"vision", "document_ai", "speech_to_text"}
    if scenario == "deep":
        return bool(record.eligible_services)
    custom = scenario_features.get(scenario, {})
    return record.recommended_service in custom


def scenario_service_features(scenario: str, service: str, record: AIFileRecord, scenario_features: Dict[str, Dict[str, List[str]]]) -> List[str]:
    configured = scenario_features.get(scenario, {}).get(service)
    if configured:
        return configured
    if scenario == "cheap" and service == "vision":
        return ["text_detection"]
    if scenario == "balanced" and service == "vision":
        return ["label_detection", "text_detection"]
    if scenario == "deep":
        return record.recommended_features
    return record.recommended_features[:1]


def units_for(record: AIFileRecord, service: str) -> float:
    if service == "vision":
        return max(1, record.image_count_estimated)
    if service == "document_ai":
        return max(1, record.page_count_exact or record.page_count_estimated)
    if service == "video_intelligence":
        return max(1.0, record.video_duration_seconds / 60.0)
    if service == "speech_to_text":
        return max(1.0, (record.audio_duration_seconds or record.video_duration_seconds) / 60.0)
    return 1.0


def sample_plan(records: List[AIFileRecord], sample_size: int, random_seed: int) -> List[AIFileRecord]:
    candidates = [record for record in records if record.eligibility_status in {"CLOUD_RECOMMENDED", "SKIPPED_SENSITIVE_REQUIRES_APPROVAL"}]
    rng = random.Random(random_seed)
    groups: Dict[str, List[AIFileRecord]] = {}
    for record in candidates:
        groups.setdefault(record.recommended_service or "review", []).append(record)
    chosen: List[AIFileRecord] = []
    per_group = max(1, sample_size // max(1, len(groups)))
    for group_records in groups.values():
        sorted_group = sorted(group_records, key=lambda item: item.file_id)
        rng.shuffle(sorted_group)
        chosen.extend(sorted_group[:per_group])
    return sorted(chosen[:sample_size], key=lambda item: (item.recommended_service, item.file_id))


def write_run_log(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
