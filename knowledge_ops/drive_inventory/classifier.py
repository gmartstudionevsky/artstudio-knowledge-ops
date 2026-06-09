from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from knowledge_ops.drive_inventory.config import InventoryConfig
from knowledge_ops.drive_inventory.models import DriveInventoryItem
from knowledge_ops.drive_inventory.normalizer import normalize_name


UNKNOWN_VALUES = {
    "object_suggestion": {"", "объект не определён", "unknown"},
    "department_suggestion": {"", "не определено", "Unknown", "unknown"},
    "function_suggestion": {"", "не определено", "unknown"},
    "document_family_suggestion": {"", "неизвестно", "unknown"},
    "document_type_suggestion": {"", "неизвестно", "unknown", "unknown_document", "unknown_pdf"},
    "process_suggestion": {"", "не определено", "unknown"},
    "audience_suggestion": {"", "не определено", "внутреннее использование", "unknown"},
    "sensitivity_suggestion": {"", "unknown"},
    "lifecycle_status": {"", "unknown"},
    "cleanup_category": {"", "unknown_review"},
    "source_origin": {"", "unknown_origin"},
    "media_subtype": {""},
    "image_subtype": {""},
    "video_subtype": {""},
    "audio_subtype": {""},
    "design_source_subtype": {""},
    "priority_for_human_review": {"", "normal"},
}

FAMILY_BY_TYPE = {
    "owner_management_contract": "contract",
    "rental_contract": "contract",
    "agency_contract": "contract",
    "technical_maintenance_contract": "contract",
    "purchase_sale_contract": "contract",
    "DDU": "contract",
    "lease_contract": "contract",
    "service_contract": "contract",
    "supplier_contract": "contract",
    "contractor_contract": "contract",
    "corporate_client_contract": "contract",
    "furniture_contract": "contract",
    "addendum": "contract",
    "agreement": "contract",
    "power_of_attorney": "legal_document",
    "acceptance_transfer_act": "act",
    "return_act": "act",
    "service_completion_act": "act",
    "work_completion_act": "act",
    "damage_act": "act",
    "reconciliation_act": "act",
    "inspection_act": "act",
    "defect_act": "act",
    "commissioning_act": "act",
    "apartment_registry": "registry",
    "owner_registry": "registry",
    "managed_units_registry": "registry",
    "cadastral_registry": "registry",
    "owner_income_report": "owner_document",
    "owner_payout_report": "owner_document",
    "owner_EGRN_extract": "egrn_cadastre_document",
    "owner_PIB_document": "egrn_cadastre_document",
    "invoice": "financial_document",
    "invoice_factura": "accounting_document",
    "payment_order": "financial_document",
    "receipt": "financial_document",
    "UPD": "accounting_document",
    "timesheet": "HR_document",
    "employment_contract": "HR_document",
    "job_description": "HR_document",
    "brandbook": "brand_asset",
    "logo": "brand_asset",
    "SMM_photo": "photo_asset",
    "SMM_video": "video_asset",
    "room_photo": "photo_asset",
    "public_area_photo": "photo_asset",
    "AI_EPS_SVG_source": "brand_asset",
    "checkin_sop": "standard_sop",
    "cleaning_checklist": "checklist",
    "guest_registration_instruction": "instruction",
    "procurement_invoice": "financial_document",
    "consumer_corner_document": "official_mandatory_document",
    "monthly_report": "report",
    "system_file": "system_file",
    "backup_file": "archive",
}


@dataclass(frozen=True)
class ClassificationRule:
    rule_id: str
    source: str
    tokens: tuple[str, ...] = ()
    regex_patterns: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    mime_prefixes: tuple[str, ...] = ()
    target_fields: Dict[str, Any] = field(default_factory=dict)
    weight: int = 1


@dataclass
class RuleHit:
    rule: ClassificationRule
    score: float
    source: str
    reason: str


class MetadataClassifier:
    def __init__(self, config: Optional[InventoryConfig] = None):
        self.config = config or InventoryConfig()
        self.rules_by_source = {
            "path": load_rules(self.config.path_rules_config, "path"),
            "filename": load_rules(self.config.filename_rules_config, "filename"),
            "extension": load_rules(self.config.extension_rules_config, "extension"),
            "sensitivity": load_rules(self.config.sensitivity_rules_config, "sensitivity"),
            "media": load_rules(self.config.media_rules_config, "media"),
            "cleanup": load_rules(self.config.cleanup_rules_config, "cleanup"),
        }

    def classify(self, item: DriveInventoryItem) -> DriveInventoryItem:
        if item.is_google_sheet_skipped:
            item.classification_status = "CLASSIFIED_METADATA_MEDIUM"
            item.cleanup_category = "skip_google_sheet"
            item.priority_for_human_review = "low"
            return item

        hits: List[RuleHit] = []
        hits.extend(self._path_hits(item))
        hits.extend(self._text_hits(item, "filename", item.name))
        hits.extend(self._extension_hits(item))
        hits.extend(self._text_hits(item, "sensitivity", f"{item.full_path} {item.name}"))
        hits.extend(self._mixed_hits(item, "media"))
        hits.extend(self._mixed_hits(item, "cleanup"))

        apply_hits(item, hits)
        finalize_item(item, hits)
        return item

    def _path_hits(self, item: DriveInventoryItem) -> List[RuleHit]:
        segments = [segment for segment in item.full_path.split("/") if segment]
        hits = []
        total = max(1, len(segments))
        for index, segment in enumerate(segments):
            normalized = normalize_name(segment)
            depth_weight = path_depth_weight(index, total)
            for rule in self.rules_by_source["path"]:
                if rule_matches_text(rule, normalized, segment):
                    hits.append(RuleHit(rule, rule.weight * depth_weight, "path", f"{rule.rule_id}@segment[{index}]={segment}"))
        return hits

    def _text_hits(self, item: DriveInventoryItem, source: str, text: str) -> List[RuleHit]:
        normalized = normalize_name(text)
        hits = []
        for rule in self.rules_by_source[source]:
            if rule_matches_text(rule, normalized, text):
                hits.append(RuleHit(rule, rule.weight * source_weight(source), source, f"{rule.rule_id}@{source}"))
        return hits

    def _extension_hits(self, item: DriveInventoryItem) -> List[RuleHit]:
        hits = []
        extension = normalize_name(item.extension)
        mime_type = (item.mime_type or "").lower()
        for rule in self.rules_by_source["extension"]:
            if extension_matches(rule, extension, mime_type):
                hits.append(RuleHit(rule, rule.weight * source_weight("extension"), "extension", f"{rule.rule_id}@{extension or mime_type}"))
        return hits

    def _mixed_hits(self, item: DriveInventoryItem, source: str) -> List[RuleHit]:
        text = f"{item.full_path} {item.name}"
        normalized = normalize_name(text)
        extension = normalize_name(item.extension)
        mime_type = (item.mime_type or "").lower()
        hits = []
        for rule in self.rules_by_source[source]:
            text_match = rule_matches_text(rule, normalized, text) if (rule.tokens or rule.regex_patterns) else False
            ext_match = extension_matches(rule, extension, mime_type) if (rule.extensions or rule.mime_prefixes) else False
            if (rule.tokens or rule.regex_patterns) and (rule.extensions or rule.mime_prefixes):
                matched = text_match and ext_match
            else:
                matched = text_match or ext_match
            if matched:
                hits.append(RuleHit(rule, rule.weight * source_weight(source), source, f"{rule.rule_id}@{source}"))
        return hits


def load_rules(path: str | Path, source: str) -> List[ClassificationRule]:
    config_path = Path(path)
    if not config_path.exists():
        return []
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    rules = []
    for item in data.get("rules", []):
        rules.append(
            ClassificationRule(
                rule_id=item["rule_id"],
                source=source,
                tokens=tuple(item.get("tokens", []) or []),
                regex_patterns=tuple(item.get("regex_patterns", []) or []),
                extensions=tuple(normalize_name(value).lstrip(".") for value in item.get("extensions", []) or []),
                mime_prefixes=tuple(str(value).lower() for value in item.get("mime_prefixes", []) or []),
                target_fields=item.get("target_fields", {}) or {},
                weight=int(item.get("weight", 1)),
            )
        )
    return rules


def rule_matches_text(rule: ClassificationRule, normalized_text: str, raw_text: str) -> bool:
    padded = f" {normalized_text} "
    for token in rule.tokens:
        normalized_token = normalize_name(token)
        if not normalized_token:
            continue
        if " " in normalized_token or any(not char.isalnum() and not char.isspace() for char in normalized_token):
            if normalized_token in padded:
                return True
            continue
        if re.search(rf"(?<!\w){re.escape(normalized_token)}(?!\w)", padded, flags=re.UNICODE):
            return True
    return any(re.search(pattern, raw_text, flags=re.IGNORECASE | re.MULTILINE) for pattern in rule.regex_patterns)


def extension_matches(rule: ClassificationRule, extension: str, mime_type: str) -> bool:
    return extension in rule.extensions or any(mime_type.startswith(prefix) for prefix in rule.mime_prefixes)


def path_depth_weight(index: int, total: int) -> float:
    if index <= 1:
        return 1.7
    if index >= total - 2:
        return 1.4
    return 1.0


def source_weight(source: str) -> float:
    return {
        "path": 3.0,
        "filename": 2.0,
        "sensitivity": 2.5,
        "media": 1.5,
        "cleanup": 2.0,
        "extension": 1.0,
    }.get(source, 1.0)


def apply_hits(item: DriveInventoryItem, hits: List[RuleHit]) -> None:
    scores: Dict[str, Dict[Any, float]] = defaultdict(lambda: defaultdict(float))
    field_sources: Dict[str, Dict[str, set[Any]]] = defaultdict(lambda: defaultdict(set))
    for hit in hits:
        for field_name, value in hit.rule.target_fields.items():
            if value in (None, ""):
                continue
            scores[field_name][value] += hit.score
            field_sources[field_name][hit.source].add(value)

    for field_name, value_scores in scores.items():
        best_value = sorted(value_scores.items(), key=lambda pair: (-pair[1], str(pair[0])))[0][0]
        if field_name == "cloud_analysis_candidate":
            setattr(item, field_name, bool(best_value))
        else:
            setattr(item, field_name, best_value)

    conflicts = []
    for field_name, sources in field_sources.items():
        path_values = sources.get("path", set())
        filename_values = sources.get("filename", set())
        if path_values and filename_values and path_values.isdisjoint(filename_values):
            conflicts.append(field_name)

    item.matched_path_rules = ";".join(hit.reason for hit in hits if hit.source == "path")
    item.matched_filename_rules = ";".join(hit.reason for hit in hits if hit.source == "filename")
    item.matched_extension_rules = ";".join(hit.reason for hit in hits if hit.source == "extension")
    item.matched_sensitivity_rules = ";".join(hit.reason for hit in hits if hit.source == "sensitivity")
    item.conflict_flags = ";".join(sorted(set(conflicts)))
    item.path_confidence = confidence_from_hits([hit for hit in hits if hit.source == "path"])
    item.filename_confidence = confidence_from_hits([hit for hit in hits if hit.source == "filename"])
    item.extension_confidence = confidence_from_hits([hit for hit in hits if hit.source == "extension"])


def finalize_item(item: DriveInventoryItem, hits: List[RuleHit]) -> None:
    family_from_type = FAMILY_BY_TYPE.get(item.document_type_suggestion)
    if family_from_type:
        item.document_family_suggestion = family_from_type
    if item.document_family_suggestion in {"", "неизвестно", "unknown"}:
        item.document_family_suggestion = FAMILY_BY_TYPE.get(item.document_type_suggestion, item.document_family_suggestion)
    if item.document_type_suggestion == "technical_maintenance_contract":
        item.process_suggestion = "technical_maintenance"
        item.function_suggestion = "owner_technical_maintenance"
    if item.sensitivity_suggestion in {"owner_data", "owner_contract", "guest_data", "employee_data", "personal_data", "EGRN_sensitive", "legal_contract", "financial", "HR", "security"}:
        item.action_recommendation = "SENSITIVE_REVIEW_REQUIRED"
    elif item.cleanup_category in {"system_trash_candidate", "temp_file_candidate"}:
        item.action_recommendation = "REVIEW_REQUIRED"
    else:
        item.action_recommendation = "REVIEW_REQUIRED"

    if item.cleanup_category == "system_trash_candidate":
        item.classification_status = "CLASSIFIED_SYSTEM_TRASH"
    elif item.conflict_flags:
        item.classification_status = "CONFLICT_METADATA"
    elif item.sensitivity_suggestion not in {"", "unknown", "operational", "public_internal"}:
        item.classification_status = "CLASSIFIED_SENSITIVE"
    elif item.path_confidence == "high":
        item.classification_status = "CLASSIFIED_PATH_HIGH"
    elif item.filename_confidence == "high":
        item.classification_status = "CLASSIFIED_FILENAME_HIGH"
    elif item.extension_confidence:
        item.classification_status = "CLASSIFIED_EXTENSION_ONLY"
    elif is_media(item):
        item.classification_status = "CLASSIFIED_MEDIA_METADATA"
    elif hits:
        item.classification_status = "CLASSIFIED_METADATA_MEDIUM"
    else:
        item.classification_status = "UNKNOWN"

    unknown_core = [
        item.object_suggestion in UNKNOWN_VALUES["object_suggestion"],
        item.department_suggestion in UNKNOWN_VALUES["department_suggestion"],
        item.document_type_suggestion in UNKNOWN_VALUES["document_type_suggestion"],
    ]
    if item.classification_status != "CLASSIFIED_SYSTEM_TRASH" and sum(unknown_core) >= 2:
        item.classification_status = "NEEDS_REVIEW" if hits else "UNKNOWN"

    item.combined_confidence = combined_confidence(item)
    item.confidence = item.combined_confidence
    item.retention_suggestion = retention_for(item)
    item.reason = build_reason(item, hits)


def confidence_from_hits(hits: List[RuleHit]) -> str:
    if not hits:
        return ""
    score = sum(hit.score for hit in hits)
    if score >= 25:
        return "high"
    if score >= 8:
        return "medium"
    return "low"


def combined_confidence(item: DriveInventoryItem) -> str:
    if item.conflict_flags:
        return "needs_review"
    known = [
        item.object_suggestion not in UNKNOWN_VALUES["object_suggestion"],
        item.department_suggestion not in UNKNOWN_VALUES["department_suggestion"],
        item.document_type_suggestion not in UNKNOWN_VALUES["document_type_suggestion"],
        item.sensitivity_suggestion not in UNKNOWN_VALUES["sensitivity_suggestion"],
    ]
    if item.path_confidence == "high" and item.filename_confidence in {"medium", "high"} and sum(known) >= 3:
        return "high"
    if item.path_confidence in {"medium", "high"} or item.filename_confidence in {"medium", "high"}:
        return "medium"
    if item.extension_confidence:
        return "low"
    return "unknown"


def retention_for(item: DriveInventoryItem) -> str:
    if item.cleanup_category in {"system_trash_candidate", "temp_file_candidate"}:
        return "short_term_review"
    if item.sensitivity_suggestion in {"legal_contract", "owner_contract", "financial", "accounting", "HR", "employee_data", "owner_data", "EGRN_sensitive"}:
        return "controlled_retention_review"
    if item.lifecycle_status in {"archive", "old_version", "historical"}:
        return "archive_review"
    return "standard_review"


def is_media(item: DriveInventoryItem) -> bool:
    return item.document_family_suggestion in {"media_asset", "photo_asset", "video_asset", "audio_asset", "brand_asset"} or bool(item.media_subtype)


def build_reason(item: DriveInventoryItem, hits: List[RuleHit]) -> str:
    if not hits:
        return "No confident metadata classification rule matched."
    parts = []
    for field_name in [
        "object_suggestion",
        "department_suggestion",
        "function_suggestion",
        "document_family_suggestion",
        "document_type_suggestion",
        "process_suggestion",
        "sensitivity_suggestion",
        "lifecycle_status",
        "cleanup_category",
        "source_origin",
        "media_subtype",
    ]:
        value = getattr(item, field_name)
        if value not in UNKNOWN_VALUES.get(field_name, {""}):
            parts.append(f"{field_name}={value}")
    sources = ",".join(sorted({hit.source for hit in hits}))
    parts.append(f"sources={sources}")
    if item.conflict_flags:
        parts.append(f"conflicts={item.conflict_flags}")
    return "; ".join(parts)


_DEFAULT_CLASSIFIER: Optional[MetadataClassifier] = None


def classify_item(item: DriveInventoryItem, classifier: Optional[MetadataClassifier] = None) -> DriveInventoryItem:
    global _DEFAULT_CLASSIFIER
    if classifier is None:
        if _DEFAULT_CLASSIFIER is None:
            _DEFAULT_CLASSIFIER = MetadataClassifier()
        classifier = _DEFAULT_CLASSIFIER
    return classifier.classify(item)
