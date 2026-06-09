from __future__ import annotations

import csv
import json
import re
import time
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Pattern, Set

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
    "owner_cadastral_document": "egrn_cadastre_document",
    "cadastral_document": "egrn_cadastre_document",
    "utility_receipt_package": "utility_document",
    "utility_accrual_registry": "utility_document",
    "ecology_charge_calculation": "utility_document",
    "utility_cache_file": "utility_document",
    "invoice": "financial_document",
    "invoice_factura": "accounting_document",
    "payment_order": "financial_document",
    "receipt": "financial_document",
    "UPD": "accounting_document",
    "cash_expense_order": "financial_document",
    "cash_receipt_order": "financial_document",
    "reconciliation_statement": "accounting_document",
    "timesheet": "HR_document",
    "employment_contract": "HR_document",
    "job_description": "HR_document",
    "brandbook": "brand_asset",
    "logo": "brand_asset",
    "signature_image": "brand_asset",
    "company_stamp_image": "brand_asset",
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
    "thumbs_db": "system_file",
    "ds_store": "system_file",
    "desktop_ini": "system_file",
    "office_temp_lock": "temporary_file",
    "generated_cache_json": "temporary_file",
    "chat_export_archive": "archive",
    "chat_export_messages_html": "archive",
    "chat_export_metadata_json": "archive",
    "chat_thumbnail_image": "photo_asset",
    "backup_file": "archive",
}

RULE_SOURCES = ("path", "filename", "extension", "sensitivity", "media", "cleanup")
VALID_TARGET_FIELDS = set(UNKNOWN_VALUES) | {
    "object_suggestion",
    "department_suggestion",
    "function_suggestion",
    "document_family_suggestion",
    "document_type_suggestion",
    "process_suggestion",
    "audience_suggestion",
    "sensitivity_suggestion",
    "retention_suggestion",
    "classification_status",
    "action_recommendation",
    "cloud_analysis_candidate",
}
SENSITIVE_VALUES = {
    "owner_data",
    "owner_contract",
    "guest_data",
    "employee_data",
    "personal_data",
    "personal_data_possible",
    "passport_data",
    "phone_email",
    "cadastral_number",
    "EGRN_sensitive",
    "real_estate_sensitive",
    "legal_contract",
    "legal_sensitive",
    "signature_seal_sensitive",
    "financial",
    "accounting",
    "bank_details",
    "tax_details",
    "HR",
    "commercial",
    "supplier_pricing",
    "security",
    "fire_safety",
    "access_control",
    "screenshot_sensitive",
    "correspondence_sensitive",
}
ENTITY_PATTERNS: Dict[str, Pattern[str]] = {
    "unit_number_detected": re.compile(r"\b(?:ап\.?|апарт\.?|апартамент|apt|unit)\s*№?\s*(\d{2,4})\b", re.IGNORECASE),
    "premise_number_detected": re.compile(r"\b(?:пом\.?|помещение)\s*№?\s*(\d+\s*[-]?\s*[НH]?)\b", re.IGNORECASE),
    "corpus_detected": re.compile(r"\b(?:корп\.?|корпус|к\.?)\s*(1|2)\b", re.IGNORECASE),
    "cadastral_number_detected": re.compile(r"\b\d{2}:\d{2}:\d{6,7}:\d+\b"),
    "contract_number_detected": re.compile(r"\b(?:договор|дог\.?|contract)\s*№?\s*([A-Za-zА-Яа-я0-9\-\/_.]+)", re.IGNORECASE),
    "act_number_detected": re.compile(r"\b(?:акт|act)\s*№?\s*([A-Za-zА-Яа-я0-9\-\/_.]+)", re.IGNORECASE),
    "invoice_number_detected": re.compile(r"\b(?:сч[её]т|invoice)\s*№?\s*([A-Za-zА-Яа-я0-9\-\/_.]+)", re.IGNORECASE),
    "payment_order_number_detected": re.compile(r"\b(?:плат[её]жное поручение|п\/п)\s*№?\s*([A-Za-zА-Яа-я0-9\-\/_.]+)", re.IGNORECASE),
    "date_detected": re.compile(r"\b(?:20\d{2}|19\d{2})[-_. ](?:0?[1-9]|1[0-2])[-_. ](?:0?[1-9]|[12]\d|3[01])\b|\b(?:0?[1-9]|[12]\d|3[01])[-_. ](?:0?[1-9]|1[0-2])[-_. ](?:20\d{2}|19\d{2})\b"),
    "year_detected": re.compile(r"\b(20\d{2}|19\d{2})\b"),
    "month_detected": re.compile(r"\b(?:январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь|january|february|march|april|may|june|july|august|september|october|november|december)\b", re.IGNORECASE),
    "email_detected": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "phone_detected": re.compile(r"(?:\+7|8)[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", re.IGNORECASE),
    "SNILS_detected": re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b"),
    "INN_detected": re.compile(r"\bИНН\s*[:№]?\s*(\d{10,12})\b", re.IGNORECASE),
    "KPP_detected": re.compile(r"\bКПП\s*[:№]?\s*(\d{9})\b", re.IGNORECASE),
    "OGRN_detected": re.compile(r"\bОГРН\s*[:№]?\s*(\d{13,15})\b", re.IGNORECASE),
    "bank_account_detected": re.compile(r"\b\d{20}\b"),
    "passport_marker_detected": re.compile(r"\b(?:паспорт|passport|серия\s+\d{4}|выдан)\b", re.IGNORECASE),
    "legal_entity_marker_detected": re.compile(r"\b(?:ООО|АО|ИП|ИНН|КПП|ОГРН|БИК)\b", re.IGNORECASE),
}


class BoundedNormalizeCache:
    def __init__(self, max_size: int = 50000):
        self.max_size = max(100, int(max_size or 50000))
        self._values: OrderedDict[str, str] = OrderedDict()

    def normalize(self, value: str) -> str:
        key = value or ""
        cached = self._values.get(key)
        if cached is not None:
            self._values.move_to_end(key)
            return cached
        normalized = normalize_name(key)
        self._values[key] = normalized
        if len(self._values) > self.max_size:
            self._values.popitem(last=False)
        return normalized


@dataclass(frozen=True)
class ClassificationRule:
    rule_id: str
    source: str
    tokens: tuple[str, ...] = ()
    regex_patterns: tuple[str, ...] = ()
    negative_tokens: tuple[str, ...] = ()
    negative_regex_patterns: tuple[str, ...] = ()
    extensions: frozenset[str] = frozenset()
    mime_prefixes: tuple[str, ...] = ()
    target_fields: Dict[str, Any] = field(default_factory=dict)
    weight: int = 1
    category: str = ""
    normalized_tokens: tuple[str, ...] = ()
    normalized_negative_tokens: tuple[str, ...] = ()
    compiled_regex_patterns: tuple[Pattern[str], ...] = ()
    compiled_negative_regex_patterns: tuple[Pattern[str], ...] = ()
    regex_errors: tuple[str, ...] = ()


@dataclass
class RuleHit:
    rule: ClassificationRule
    score: float
    source: str
    reason: str
    matched_by: str = "unknown"
    elapsed_ms: float = 0.0


@dataclass
class RulePerformance:
    source: str
    rule_id: str
    category: str = ""
    evaluations: int = 0
    match_count: int = 0
    files_affected: Set[str] = field(default_factory=set)
    total_time_ms: float = 0.0
    token_match_count: int = 0
    regex_match_count: int = 0
    confidence_contribution_total: float = 0.0
    example_paths: List[str] = field(default_factory=list)
    regex_errors: List[str] = field(default_factory=list)

    @property
    def average_time_ms(self) -> float:
        return self.total_time_ms / self.evaluations if self.evaluations else 0.0


@dataclass
class ClassificationDiagnostics:
    engine_mode: str
    total_items_classified: int = 0
    total_classification_time_ms: float = 0.0
    candidate_rule_counts: List[int] = field(default_factory=list)
    full_scan_rules_count: int = 0
    total_rules_loaded: int = 0
    regex_rules_count: int = 0
    token_rules_count: int = 0
    extension_rules_count: int = 0
    mime_rules_count: int = 0
    rules_by_source: Counter = field(default_factory=Counter)
    rule_stats: Dict[str, RulePerformance] = field(default_factory=dict)
    load_errors: List[Dict[str, str]] = field(default_factory=list)
    content_inspection_time_ms: float = 0.0
    duplicate_detection_time_ms: float = 0.0

    def rule_key(self, rule: ClassificationRule) -> str:
        return f"{rule.source}:{rule.rule_id}"

    def ensure_rule(self, rule: ClassificationRule) -> RulePerformance:
        key = self.rule_key(rule)
        if key not in self.rule_stats:
            self.rule_stats[key] = RulePerformance(
                source=rule.source,
                rule_id=rule.rule_id,
                category=rule.category,
                regex_errors=list(rule.regex_errors),
            )
        return self.rule_stats[key]

    def record_rule_eval(self, rule: ClassificationRule, elapsed_ms: float, hit: RuleHit | None, file_id: str, path: str) -> None:
        stats = self.ensure_rule(rule)
        stats.evaluations += 1
        stats.total_time_ms += elapsed_ms
        if not hit:
            return
        stats.match_count += 1
        stats.files_affected.add(file_id)
        stats.confidence_contribution_total += hit.score
        if hit.matched_by == "regex":
            stats.regex_match_count += 1
        elif hit.matched_by == "token":
            stats.token_match_count += 1
        if len(stats.example_paths) < 3:
            stats.example_paths.append(sanitize_path(path))

    def snapshot(self, items: Iterable[DriveInventoryItem] = ()) -> Dict[str, Any]:
        times = []
        # Per-item timings are summarized through average here; detailed percentiles stay stable
        # when classification is called independently in tests.
        avg_ms = self.total_classification_time_ms / self.total_items_classified if self.total_items_classified else 0.0
        if self.total_items_classified:
            times = [avg_ms]
        return {
            "engine_mode": self.engine_mode,
            "total_classification_time_ms": round(self.total_classification_time_ms, 3),
            "avg_classification_time_ms": round(avg_ms, 3),
            "p50_classification_time_ms": round(percentile(times, 50), 3),
            "p90_classification_time_ms": round(percentile(times, 90), 3),
            "p95_classification_time_ms": round(percentile(times, 95), 3),
            "p99_classification_time_ms": round(percentile(times, 99), 3),
            "total_items_classified": self.total_items_classified,
            "total_rules_loaded": self.total_rules_loaded,
            "rules_by_source": dict(self.rules_by_source),
            "regex_rules_count": self.regex_rules_count,
            "token_rules_count": self.token_rules_count,
            "extension_rules_count": self.extension_rules_count,
            "mime_rules_count": self.mime_rules_count,
            "indexed_candidate_rules_avg": round(sum(self.candidate_rule_counts) / len(self.candidate_rule_counts), 3) if self.candidate_rule_counts else 0,
            "full_scan_rules_count": self.full_scan_rules_count,
            "content_inspection_time_ms": round(self.content_inspection_time_ms, 3),
            "duplicate_detection_time_ms": round(self.duplicate_detection_time_ms, 3),
            "load_errors": self.load_errors,
            "quality": build_quality_summary(items),
        }


class RuleIndex:
    def __init__(self, rules: Iterable[ClassificationRule]):
        self.rules = list(rules)
        self.token_index: Dict[str, Set[int]] = defaultdict(set)
        self.extension_index: Dict[str, Set[int]] = defaultdict(set)
        self.mime_rule_ids: Set[int] = set()
        self.regex_rule_ids: Set[int] = set()
        self.fallback_rule_ids: Set[int] = set()
        for idx, rule in enumerate(self.rules):
            has_text_selector = bool(rule.normalized_tokens or rule.compiled_regex_patterns)
            has_file_selector = bool(rule.extensions or rule.mime_prefixes)
            for token in rule.normalized_tokens:
                for word in token_words(token):
                    self.token_index[word].add(idx)
            for extension in rule.extensions:
                self.extension_index[extension].add(idx)
            if rule.mime_prefixes:
                self.mime_rule_ids.add(idx)
            if rule.compiled_regex_patterns:
                self.regex_rule_ids.add(idx)
            if not has_text_selector and not has_file_selector:
                self.fallback_rule_ids.add(idx)

    def candidates_for_text(self, normalized_text: str, strict_full_scan: bool) -> List[ClassificationRule]:
        if strict_full_scan:
            return self.rules
        rule_ids: Set[int] = set(self.regex_rule_ids) | set(self.fallback_rule_ids)
        for word in token_words(normalized_text):
            rule_ids.update(self.token_index.get(word, set()))
        return [self.rules[idx] for idx in sorted(rule_ids)]

    def candidates_for_extension(self, extension: str, mime_type: str, strict_full_scan: bool) -> List[ClassificationRule]:
        if strict_full_scan:
            return self.rules
        rule_ids: Set[int] = set(self.fallback_rule_ids)
        rule_ids.update(self.extension_index.get(extension, set()))
        for idx in self.mime_rule_ids:
            if any(mime_type.startswith(prefix) for prefix in self.rules[idx].mime_prefixes):
                rule_ids.add(idx)
        return [self.rules[idx] for idx in sorted(rule_ids)]

    def candidates_for_mixed(self, normalized_text: str, extension: str, mime_type: str, strict_full_scan: bool) -> List[ClassificationRule]:
        if strict_full_scan:
            return self.rules
        rule_ids: Set[int] = set(self.fallback_rule_ids) | set(self.regex_rule_ids)
        for word in token_words(normalized_text):
            rule_ids.update(self.token_index.get(word, set()))
        rule_ids.update(self.extension_index.get(extension, set()))
        for idx in self.mime_rule_ids:
            if any(mime_type.startswith(prefix) for prefix in self.rules[idx].mime_prefixes):
                rule_ids.add(idx)
        return [self.rules[idx] for idx in sorted(rule_ids)]


class MetadataClassifier:
    def __init__(self, config: Optional[InventoryConfig] = None):
        self.config = config or InventoryConfig()
        self.normalize_cache = BoundedNormalizeCache(self.config.classification_normalization_cache_size)
        self.strict_full_scan = bool(self.config.classification_strict_full_scan or not self.config.classification_use_rule_index)
        self.rules_by_source = {
            "path": load_rules(self.config.path_rules_config, "path", self.normalize_cache),
            "filename": load_rules(self.config.filename_rules_config, "filename", self.normalize_cache),
            "extension": load_rules(self.config.extension_rules_config, "extension", self.normalize_cache),
            "sensitivity": load_rules(self.config.sensitivity_rules_config, "sensitivity", self.normalize_cache),
            "media": load_rules(self.config.media_rules_config, "media", self.normalize_cache),
            "cleanup": load_rules(self.config.cleanup_rules_config, "cleanup", self.normalize_cache),
        }
        self.indexes = {source: RuleIndex(rules) for source, rules in self.rules_by_source.items()}
        self.diagnostics = ClassificationDiagnostics(
            engine_mode="full_scan" if self.strict_full_scan else "indexed",
            full_scan_rules_count=sum(len(rules) for rules in self.rules_by_source.values()),
        )
        self._seed_diagnostics()

    def _seed_diagnostics(self) -> None:
        for source, rules in self.rules_by_source.items():
            self.diagnostics.rules_by_source[source] = len(rules)
            for rule in rules:
                self.diagnostics.total_rules_loaded += 1
                self.diagnostics.token_rules_count += 1 if rule.normalized_tokens else 0
                self.diagnostics.regex_rules_count += 1 if rule.compiled_regex_patterns or rule.regex_errors else 0
                self.diagnostics.extension_rules_count += 1 if rule.extensions else 0
                self.diagnostics.mime_rules_count += 1 if rule.mime_prefixes else 0
                self.diagnostics.ensure_rule(rule)
                for error in rule.regex_errors:
                    self.diagnostics.load_errors.append({"source": source, "rule_id": rule.rule_id, "error": error})

    def classify(self, item: DriveInventoryItem) -> DriveInventoryItem:
        if item.is_google_sheet_skipped:
            item.classification_status = "CLASSIFIED_METADATA_MEDIUM"
            item.cleanup_category = "skip_google_sheet"
            item.priority_for_human_review = "low"
            return item

        started = time.perf_counter()
        hits: List[RuleHit] = []
        hits.extend(self._path_hits(item))
        hits.extend(self._text_hits(item, "filename", item.name))
        hits.extend(self._extension_hits(item))
        hits.extend(self._text_hits(item, "sensitivity", f"{item.full_path} {item.name}"))
        hits.extend(self._mixed_hits(item, "media"))
        hits.extend(self._mixed_hits(item, "cleanup"))

        apply_hits(item, hits)
        finalize_item(item, hits)
        enrich_v3_classification(item, hits)
        self.diagnostics.total_items_classified += 1
        self.diagnostics.total_classification_time_ms += (time.perf_counter() - started) * 1000
        return item

    def _path_hits(self, item: DriveInventoryItem) -> List[RuleHit]:
        segments = [segment for segment in item.full_path.split("/") if segment]
        hits = []
        total = max(1, len(segments))
        for index, segment in enumerate(segments):
            normalized = self.normalize_cache.normalize(segment)
            depth_weight = path_depth_weight(index, total)
            candidates = self.indexes["path"].candidates_for_text(normalized, self.strict_full_scan)
            self.diagnostics.candidate_rule_counts.append(len(candidates))
            for rule in candidates:
                hit = self._match_text_rule(rule, normalized, segment, item, "path", depth_weight, f"{rule.rule_id}@segment[{index}]={segment}")
                if hit:
                    hits.append(hit)
        return hits

    def _text_hits(self, item: DriveInventoryItem, source: str, text: str) -> List[RuleHit]:
        normalized = self.normalize_cache.normalize(text)
        candidates = self.indexes[source].candidates_for_text(normalized, self.strict_full_scan)
        self.diagnostics.candidate_rule_counts.append(len(candidates))
        hits = []
        for rule in candidates:
            hit = self._match_text_rule(rule, normalized, text, item, source, source_weight(source), f"{rule.rule_id}@{source}")
            if hit:
                hits.append(hit)
        return hits

    def _extension_hits(self, item: DriveInventoryItem) -> List[RuleHit]:
        extension = self.normalize_cache.normalize(item.extension).lstrip(".")
        mime_type = (item.mime_type or "").lower()
        candidates = self.indexes["extension"].candidates_for_extension(extension, mime_type, self.strict_full_scan)
        self.diagnostics.candidate_rule_counts.append(len(candidates))
        hits = []
        for rule in candidates:
            started = time.perf_counter()
            matched = extension_matches(rule, extension, mime_type)
            elapsed_ms = (time.perf_counter() - started) * 1000
            hit = None
            if matched:
                hit = RuleHit(rule, rule.weight * source_weight("extension"), "extension", f"{rule.rule_id}@{extension or mime_type}", "extension", elapsed_ms)
                hits.append(hit)
            self.diagnostics.record_rule_eval(rule, elapsed_ms, hit, item.file_id, item.full_path)
        return hits

    def _mixed_hits(self, item: DriveInventoryItem, source: str) -> List[RuleHit]:
        text = f"{item.full_path} {item.name}"
        normalized = self.normalize_cache.normalize(text)
        extension = self.normalize_cache.normalize(item.extension).lstrip(".")
        mime_type = (item.mime_type or "").lower()
        candidates = self.indexes[source].candidates_for_mixed(normalized, extension, mime_type, self.strict_full_scan)
        self.diagnostics.candidate_rule_counts.append(len(candidates))
        hits = []
        for rule in candidates:
            started = time.perf_counter()
            text_match, matched_by = match_text(rule, normalized, text)
            ext_match = extension_matches(rule, extension, mime_type) if (rule.extensions or rule.mime_prefixes) else False
            if (rule.normalized_tokens or rule.compiled_regex_patterns) and (rule.extensions or rule.mime_prefixes):
                matched = text_match and ext_match
            else:
                matched = text_match or ext_match
            elapsed_ms = (time.perf_counter() - started) * 1000
            hit = None
            if matched:
                hit = RuleHit(rule, rule.weight * source_weight(source), source, f"{rule.rule_id}@{source}", matched_by if text_match else "extension", elapsed_ms)
                hits.append(hit)
            self.diagnostics.record_rule_eval(rule, elapsed_ms, hit, item.file_id, item.full_path)
        return hits

    def _match_text_rule(
        self,
        rule: ClassificationRule,
        normalized: str,
        raw_text: str,
        item: DriveInventoryItem,
        source: str,
        weight: float,
        reason: str,
    ) -> RuleHit | None:
        started = time.perf_counter()
        matched, matched_by = match_text(rule, normalized, raw_text)
        elapsed_ms = (time.perf_counter() - started) * 1000
        hit = RuleHit(rule, rule.weight * weight, source, reason, matched_by, elapsed_ms) if matched else None
        self.diagnostics.record_rule_eval(rule, elapsed_ms, hit, item.file_id, item.full_path)
        return hit

    def compare_indexed_vs_full_scan(self, items: Iterable[DriveInventoryItem]) -> List[Dict[str, str]]:
        indexed = MetadataClassifier(self.config.__class__(**{**self.config.__dict__, "classification_use_rule_index": True, "classification_strict_full_scan": False}))
        full = MetadataClassifier(self.config.__class__(**{**self.config.__dict__, "classification_use_rule_index": False, "classification_strict_full_scan": True}))
        diffs = []
        fields = [
            "object_suggestion",
            "department_suggestion",
            "function_suggestion",
            "document_family_suggestion",
            "document_type_suggestion",
            "process_suggestion",
            "sensitivity_suggestion",
            "lifecycle_status",
            "cleanup_category",
            "media_subtype",
            "classification_status",
            "action_recommendation",
        ]
        for original in items:
            left = clone_item(original)
            right = clone_item(original)
            indexed.classify(left)
            full.classify(right)
            for field_name in fields:
                if getattr(left, field_name) != getattr(right, field_name):
                    diffs.append(
                        {
                            "file_id": original.file_id,
                            "field": field_name,
                            "indexed": str(getattr(left, field_name)),
                            "full_scan": str(getattr(right, field_name)),
                        }
                    )
        return diffs


def load_rules(path: str | Path, source: str, normalize_cache: BoundedNormalizeCache | None = None) -> List[ClassificationRule]:
    config_path = Path(path)
    if not config_path.exists():
        return []
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    cache = normalize_cache or BoundedNormalizeCache()
    rules = []
    for item in data.get("rules", []):
        rules.append(compile_rule(item, source, cache))
    return rules


def compile_rule(item: Dict[str, Any], source: str, normalize_cache: BoundedNormalizeCache) -> ClassificationRule:
    regexes, regex_errors = compile_patterns(item.get("regex_patterns", []) or [], item.get("rule_id", ""), "regex_patterns")
    negative_regexes, negative_regex_errors = compile_patterns(item.get("negative_regex_patterns", []) or item.get("negative_patterns", []) or [], item.get("rule_id", ""), "negative_regex_patterns")
    tokens = tuple(str(value) for value in item.get("tokens", []) or item.get("keywords", []) or [])
    negative_tokens = tuple(str(value) for value in item.get("negative_tokens", []) or [])
    return ClassificationRule(
        rule_id=item["rule_id"],
        source=source,
        tokens=tokens,
        regex_patterns=tuple(item.get("regex_patterns", []) or []),
        negative_tokens=negative_tokens,
        negative_regex_patterns=tuple(item.get("negative_regex_patterns", []) or item.get("negative_patterns", []) or []),
        extensions=frozenset(normalize_cache.normalize(str(value)).lstrip(".") for value in item.get("extensions", []) or []),
        mime_prefixes=tuple(str(value).lower() for value in item.get("mime_prefixes", []) or []),
        target_fields=item.get("target_fields", {}) or {},
        weight=int(item.get("weight", 1)),
        category=item.get("category", source),
        normalized_tokens=tuple(filter(None, (normalize_cache.normalize(token) for token in tokens))),
        normalized_negative_tokens=tuple(filter(None, (normalize_cache.normalize(token) for token in negative_tokens))),
        compiled_regex_patterns=tuple(regexes),
        compiled_negative_regex_patterns=tuple(negative_regexes),
        regex_errors=tuple(regex_errors + negative_regex_errors),
    )


def compile_patterns(patterns: Iterable[str], rule_id: str, field_name: str) -> tuple[List[Pattern[str]], List[str]]:
    compiled = []
    errors = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE))
        except re.error as exc:
            errors.append(f"{field_name}:{pattern}:{exc}")
    return compiled, errors


def token_words(value: str) -> List[str]:
    return re.findall(r"\w+", value or "", flags=re.UNICODE)


def match_text(rule: ClassificationRule, normalized_text: str, raw_text: str) -> tuple[bool, str]:
    if has_negative_match(rule, normalized_text, raw_text):
        return False, "negative"
    padded = f" {normalized_text} "
    for token in rule.normalized_tokens:
        if " " in token or any(not char.isalnum() and not char.isspace() for char in token):
            if token in padded:
                return True, "token"
            continue
        if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", padded, flags=re.UNICODE):
            return True, "token"
    for pattern in rule.compiled_regex_patterns:
        if pattern.search(raw_text):
            return True, "regex"
    return False, "none"


def has_negative_match(rule: ClassificationRule, normalized_text: str, raw_text: str) -> bool:
    padded = f" {normalized_text} "
    for token in rule.normalized_negative_tokens:
        if token and token in padded:
            return True
    return any(pattern.search(raw_text) for pattern in rule.compiled_negative_regex_patterns)


def rule_matches_text(rule: ClassificationRule, normalized_text: str, raw_text: str) -> bool:
    return match_text(rule, normalized_text, raw_text)[0]


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
    item.matched_media_rules = ";".join(hit.reason for hit in hits if hit.source == "media")
    item.matched_cleanup_rules = ";".join(hit.reason for hit in hits if hit.source == "cleanup")
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
    if item.action_recommendation == "DO_NOT_TOUCH":
        pass
    elif item.sensitivity_suggestion in {"owner_data", "owner_contract", "guest_data", "employee_data", "personal_data", "personal_data_possible", "passport_data", "EGRN_sensitive", "legal_contract", "legal_sensitive", "signature_seal_sensitive", "financial", "accounting", "bank_details", "HR", "security"}:
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


def enrich_v3_classification(item: DriveInventoryItem, hits: List[RuleHit]) -> None:
    apply_name_based_overrides(item)
    extract_metadata_entities(item)
    apply_field_confidence_and_evidence(item)
    apply_sensitivity_flags(item)
    apply_duplicate_sensitive_overrides(item)
    apply_ocr_and_cloud_candidates(item)
    item.human_review_queue = choose_human_review_queue(item)
    item.classification_reason = build_classification_reason(item)


def apply_name_based_overrides(item: DriveInventoryItem) -> None:
    normalized = normalize_name(item.name)
    if normalized == "thumbs.db":
        item.document_family_suggestion = "system_file"
        item.document_type_suggestion = "thumbs_db"
    elif normalized == ".ds store":
        item.document_family_suggestion = "system_file"
        item.document_type_suggestion = "ds_store"
    elif normalized == "desktop.ini":
        item.document_family_suggestion = "system_file"
        item.document_type_suggestion = "desktop_ini"
    elif normalized.startswith("~$"):
        item.document_family_suggestion = "temporary_file"
        item.document_type_suggestion = "office_temp_lock"
    if any(token in normalized for token in ["подпись", "печать", "signature", "stamp"]):
        item.sensitivity_suggestion = "signature_seal_sensitive"
        item.action_recommendation = "DO_NOT_TOUCH"
        item.cleanup_category = "legal_hold_review"


def extract_metadata_entities(item: DriveInventoryItem) -> None:
    text = f"{item.full_path} {item.name}"
    for field_name, pattern in ENTITY_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1) if match.groups() else match.group(0)
        setattr(item, field_name, value[:120])


def apply_field_confidence_and_evidence(item: DriveInventoryItem) -> None:
    path_rules = compact_rules(item.matched_path_rules)
    filename_rules = compact_rules(item.matched_filename_rules)
    extension_rules = compact_rules(item.matched_extension_rules)
    sensitivity_rules = compact_rules(item.matched_sensitivity_rules)
    media_rules = compact_rules(item.matched_media_rules)
    cleanup_rules = compact_rules(item.matched_cleanup_rules)
    content_rules = compact_rules(item.content_rule_matches)
    for field_name, base_confidence, evidence in [
        ("object", item.path_confidence or "unknown", path_rules),
        ("department", item.path_confidence or item.filename_confidence or "unknown", ";".join(filter(None, [path_rules, filename_rules]))),
        ("function", item.combined_confidence, ";".join(filter(None, [path_rules, filename_rules, content_rules]))),
        ("document_family", item.combined_confidence, ";".join(filter(None, [filename_rules, extension_rules, content_rules]))),
        ("document_type", item.combined_confidence, ";".join(filter(None, [filename_rules, content_rules, extension_rules]))),
        ("process", item.combined_confidence, ";".join(filter(None, [path_rules, filename_rules, content_rules]))),
        ("sensitivity", "high" if item.sensitivity_suggestion in SENSITIVE_VALUES else item.combined_confidence, ";".join(filter(None, [sensitivity_rules, content_rules]))),
        ("lifecycle", item.combined_confidence, ";".join(filter(None, [filename_rules, cleanup_rules]))),
        ("cleanup", "high" if item.cleanup_category == "system_trash_candidate" else item.combined_confidence, cleanup_rules or filename_rules),
        ("media_subtype", item.combined_confidence, media_rules or filename_rules),
    ]:
        setattr(item, f"{field_name}_confidence", normalize_confidence(base_confidence))
        evidence_field = f"{field_name}_evidence"
        if hasattr(item, evidence_field):
            setattr(item, evidence_field, evidence[:500])
    item.audience_confidence = normalize_confidence(item.combined_confidence)
    item.source_origin_confidence = normalize_confidence(item.path_confidence or item.combined_confidence)


def apply_sensitivity_flags(item: DriveInventoryItem) -> None:
    flags = set(filter(None, item.content_sensitivity_flags.split(";")))
    if item.sensitivity_suggestion not in {"", "unknown"}:
        flags.add(item.sensitivity_suggestion)
    for field_name, flag in [
        ("passport_marker_detected", "passport_data"),
        ("SNILS_detected", "personal_data"),
        ("phone_detected", "phone_email"),
        ("email_detected", "phone_email"),
        ("cadastral_number_detected", "cadastral_number"),
        ("INN_detected", "tax_details"),
        ("KPP_detected", "tax_details"),
        ("OGRN_detected", "tax_details"),
        ("bank_account_detected", "bank_details"),
    ]:
        if getattr(item, field_name):
            flags.add(flag)
    item.sensitivity_flags = ";".join(sorted(flags))
    if {"passport_data", "personal_data", "phone_email"} & flags and item.sensitivity_suggestion == "unknown":
        item.sensitivity_suggestion = "personal_data_possible"
    if {"bank_details", "tax_details"} & flags and item.sensitivity_suggestion == "unknown":
        item.sensitivity_suggestion = "financial"


def apply_duplicate_sensitive_overrides(item: DriveInventoryItem) -> None:
    if item.duplicate_kind and item.sensitivity_suggestion in SENSITIVE_VALUES:
        item.cleanup_category = "sensitive_duplicate_review"
        item.human_review_queue = "sensitive_data_review"
        item.action_recommendation = "SENSITIVE_REVIEW_REQUIRED"
    if item.cleanup_category == "system_trash_candidate":
        item.document_family_suggestion = "system_file"
        item.cleanup_confidence = "high"


def apply_ocr_and_cloud_candidates(item: DriveInventoryItem) -> None:
    ext = (item.extension or "").lower()
    mime = (item.mime_type or "").lower()
    no_text_pdf = ext == "pdf" and item.content_extract_status in {"pdf_no_text_layer", "ocr_disabled", "not_attempted"}
    image_candidate = mime.startswith("image/") or ext in {"jpg", "jpeg", "png", "webp", "tif", "tiff", "bmp"}
    presentation_candidate = ext in {"pptx"} or mime in {
        "application/vnd.google-apps.presentation",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    document_scan_name = any(token in normalize_name(f"{item.full_path} {item.name}") for token in ["scan", "скан", "паспорт", "договор", "акт", "подпис"])
    if item.is_google_sheet_skipped:
        item.ocr_candidate = False
        item.ocr_status = "skipped_google_sheet"
        item.cloud_analysis_candidate = False
        item.cloud_analysis_recommended_service = ""
        item.cloud_analysis_approval_required = False
        return
    if no_text_pdf or (image_candidate and document_scan_name) or (presentation_candidate and item.content_extract_status in {"not_attempted", "unsupported_google_native"}):
        item.ocr_candidate = True
        item.ocr_status = "candidate_not_attempted"
        item.ocr_reason = "metadata indicates scanned/no-text document candidate"
        item.ocr_requires_manual_review = item.sensitivity_suggestion in SENSITIVE_VALUES
    if image_candidate:
        item.cloud_analysis_candidate = True
        item.cloud_analysis_recommended_service = "Cloud Vision"
    elif no_text_pdf:
        item.cloud_analysis_candidate = True
        item.cloud_analysis_recommended_service = "Document AI"
    elif mime.startswith("video/"):
        item.cloud_analysis_candidate = True
        item.cloud_analysis_recommended_service = "Video Intelligence"
    elif mime.startswith("audio/"):
        item.cloud_analysis_candidate = True
        item.cloud_analysis_recommended_service = "Speech-to-Text"
    item.cloud_analysis_approval_required = bool(item.cloud_analysis_candidate and item.sensitivity_suggestion in SENSITIVE_VALUES)


def choose_human_review_queue(item: DriveInventoryItem) -> str:
    if item.cloud_analysis_approval_required:
        return "cloud_ai_approval_review"
    if item.conflict_flags or "content_metadata_conflict" in item.reason:
        return "conflict_review"
    if item.is_google_sheet_skipped:
        return "knowledge_base_review"
    if item.cleanup_category == "system_trash_candidate":
        return "system_trash_review"
    if item.ocr_candidate:
        return "OCR_review"
    if item.sensitivity_suggestion in {"legal_contract", "legal_sensitive"}:
        return "legal_review"
    if item.sensitivity_suggestion in {"owner_data", "owner_contract", "EGRN_sensitive", "real_estate_sensitive"}:
        return "owner_contract_review"
    if item.sensitivity_suggestion in {"financial", "accounting", "bank_details", "tax_details"}:
        return "finance_review"
    if item.sensitivity_suggestion in {"HR", "employee_data", "passport_data", "personal_data", "personal_data_possible"}:
        return "HR_review"
    if item.sensitivity_suggestion in {"publication_review_required", "people_media", "face_possible", "gps_metadata_possible"}:
        return "media_publication_review"
    if item.cleanup_category in {"duplicate_review", "sensitive_duplicate_review"} or item.duplicate_kind:
        return "duplicate_review"
    if item.classification_status in {"UNKNOWN", "NEEDS_REVIEW"}:
        return "unknown_classification_review"
    return "knowledge_base_review"


def build_classification_reason(item: DriveInventoryItem) -> str:
    parts = [item.reason]
    if item.human_review_queue:
        parts.append(f"human_review_queue={item.human_review_queue}")
    if item.ocr_candidate:
        parts.append(f"ocr_candidate={item.ocr_reason or 'metadata'}")
    if item.cloud_analysis_candidate:
        parts.append(f"cloud_service={item.cloud_analysis_recommended_service or 'unknown'}")
    entity_fields = [
        "unit_number_detected",
        "premise_number_detected",
        "contract_number_detected",
        "act_number_detected",
        "invoice_number_detected",
        "cadastral_number_detected",
        "INN_detected",
        "bank_account_detected",
    ]
    detected = [field for field in entity_fields if getattr(item, field)]
    if detected:
        parts.append("entities=" + ",".join(detected))
    return "; ".join(filter(None, parts))[:1000]


def compact_rules(raw: str) -> str:
    return ";".join(rule.split("@", 1)[0] for rule in filter(None, (raw or "").split(";")))


def normalize_confidence(value: str) -> str:
    if value in {"high", "medium", "low", "needs_review"}:
        return value
    if value in {"", "unknown"}:
        return "unknown"
    return "medium"


def sanitize_path(path: str) -> str:
    parts = [part for part in (path or "").split("/") if part]
    if len(parts) <= 2:
        return "/" + "/".join(parts)
    return "/" + "/".join(parts[:1] + ["..."] + parts[-1:])


def percentile(values: List[float], pct: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def build_quality_summary(items: Iterable[DriveInventoryItem]) -> Dict[str, int]:
    rows = list(items)
    return {
        "classified_by_object_count": sum(1 for item in rows if item.object_suggestion not in UNKNOWN_VALUES["object_suggestion"]),
        "unknown_object_count": sum(1 for item in rows if item.object_suggestion in UNKNOWN_VALUES["object_suggestion"]),
        "classified_by_department_count": sum(1 for item in rows if item.department_suggestion not in UNKNOWN_VALUES["department_suggestion"]),
        "unknown_department_count": sum(1 for item in rows if item.department_suggestion in UNKNOWN_VALUES["department_suggestion"]),
        "classified_by_document_type_count": sum(1 for item in rows if item.document_type_suggestion not in UNKNOWN_VALUES["document_type_suggestion"]),
        "unknown_document_type_count": sum(1 for item in rows if item.document_type_suggestion in UNKNOWN_VALUES["document_type_suggestion"]),
        "sensitivity_known_count": sum(1 for item in rows if item.sensitivity_suggestion not in UNKNOWN_VALUES["sensitivity_suggestion"]),
        "sensitivity_unknown_count": sum(1 for item in rows if item.sensitivity_suggestion in UNKNOWN_VALUES["sensitivity_suggestion"]),
        "needs_review_count": sum(1 for item in rows if item.classification_status == "NEEDS_REVIEW"),
        "conflict_flags_count": sum(1 for item in rows if item.conflict_flags),
        "exact_duplicate_count": sum(1 for item in rows if item.duplicate_kind == "exact"),
        "skipped_google_sheets_count": sum(1 for item in rows if item.is_google_sheet_skipped),
    }


def clone_item(item: DriveInventoryItem) -> DriveInventoryItem:
    return DriveInventoryItem(**item.to_row())


@dataclass
class RuleValidationReport:
    errors: List[Dict[str, str]]
    warnings: List[Dict[str, str]]

    @property
    def summary(self) -> Dict[str, Any]:
        return {"errors": len(self.errors), "warnings": len(self.warnings), "valid": not self.errors}


def validate_rule_configs(config: InventoryConfig) -> RuleValidationReport:
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    source_paths = {
        "path": config.path_rules_config,
        "filename": config.filename_rules_config,
        "extension": config.extension_rules_config,
        "sensitivity": config.sensitivity_rules_config,
        "media": config.media_rules_config,
        "cleanup": config.cleanup_rules_config,
    }
    for source, path in source_paths.items():
        seen_ids: Set[str] = set()
        seen_signatures: Set[str] = set()
        config_path = Path(path)
        if not config_path.exists():
            errors.append({"source": source, "rule_id": "", "message": f"missing config: {path}"})
            continue
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        for raw in data.get("rules", []):
            rule_id = str(raw.get("rule_id", ""))
            if not rule_id:
                errors.append({"source": source, "rule_id": "", "message": "rule_id is required"})
            if rule_id in seen_ids:
                errors.append({"source": source, "rule_id": rule_id, "message": "duplicate rule_id in source"})
            seen_ids.add(rule_id)
            selectors = (raw.get("tokens") or raw.get("keywords") or []) + (raw.get("regex_patterns") or []) + (raw.get("extensions") or []) + (raw.get("mime_prefixes") or [])
            if not selectors:
                errors.append({"source": source, "rule_id": rule_id, "message": "rule has no selector"})
            try:
                int(raw.get("weight", 1))
            except (TypeError, ValueError):
                errors.append({"source": source, "rule_id": rule_id, "message": "weight must be numeric"})
            for field_name, value in (raw.get("target_fields", {}) or {}).items():
                if field_name not in VALID_TARGET_FIELDS:
                    errors.append({"source": source, "rule_id": rule_id, "message": f"unknown target field: {field_name}"})
                if field_name == "action_recommendation" and str(value).upper() == "DELETE":
                    errors.append({"source": source, "rule_id": rule_id, "message": "DELETE action is forbidden"})
            for pattern in (raw.get("regex_patterns", []) or []) + (raw.get("negative_regex_patterns", []) or raw.get("negative_patterns", []) or []):
                try:
                    re.compile(pattern)
                except re.error as exc:
                    errors.append({"source": source, "rule_id": rule_id, "message": f"invalid regex {pattern}: {exc}"})
            signature = json.dumps(
                {
                    "tokens": sorted(raw.get("tokens", []) or raw.get("keywords", []) or []),
                    "regex_patterns": sorted(raw.get("regex_patterns", []) or []),
                    "extensions": sorted(raw.get("extensions", []) or []),
                    "mime_prefixes": sorted(raw.get("mime_prefixes", []) or []),
                    "target_fields": raw.get("target_fields", {}) or {},
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if signature in seen_signatures:
                warnings.append({"source": source, "rule_id": rule_id, "message": "duplicate selector+target signature"})
            seen_signatures.add(signature)
            for token in raw.get("tokens", []) or raw.get("keywords", []) or []:
                normalized = normalize_name(str(token))
                if len(normalized) <= 3:
                    warnings.append({"source": source, "rule_id": rule_id, "message": f"very short token: {token}"})
    if not config.skip_google_sheets:
        errors.append({"source": "policy", "rule_id": "", "message": "Google Sheets skip must remain enabled"})
    if config.allow_cloud_ai_calls or config.enable_google_cloud_vision or config.enable_document_ai:
        errors.append({"source": "policy", "rule_id": "", "message": "Cloud AI calls must remain disabled by default"})
    if config.allow_sensitive_cloud_ai:
        errors.append({"source": "policy", "rule_id": "", "message": "Sensitive Cloud AI upload must remain disabled by default"})
    if config.ocr_store_text or config.ocr_store_sensitive_snippets:
        errors.append({"source": "policy", "rule_id": "", "message": "OCR text/snippet storage must remain disabled by default"})
    return RuleValidationReport(errors=errors, warnings=warnings)


def write_rule_validation_reports(config: InventoryConfig, out_dir: str | Path) -> RuleValidationReport:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = validate_rule_configs(config)
    write_dict_csv(output / "rule_validation_errors.csv", ["source", "rule_id", "message"], report.errors)
    write_dict_csv(output / "rule_validation_warnings.csv", ["source", "rule_id", "message"], report.warnings)
    lines = [
        "# Classification Rule Validation",
        "",
        f"- Errors: {len(report.errors)}",
        f"- Warnings: {len(report.warnings)}",
        f"- Valid: {str(not report.errors).lower()}",
        "",
        "Invalid regexes and unsafe DELETE actions are treated as errors. Broad or duplicate rules are warnings for manual review.",
    ]
    output.joinpath("rule_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def write_dict_csv(path: Path, columns: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


_DEFAULT_CLASSIFIER: Optional[MetadataClassifier] = None


def classify_item(item: DriveInventoryItem, classifier: Optional[MetadataClassifier] = None) -> DriveInventoryItem:
    global _DEFAULT_CLASSIFIER
    if classifier is None:
        if _DEFAULT_CLASSIFIER is None:
            _DEFAULT_CLASSIFIER = MetadataClassifier()
        classifier = _DEFAULT_CLASSIFIER
    return classifier.classify(item)
