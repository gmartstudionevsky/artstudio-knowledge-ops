from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


CORPUS_COLUMNS = [
    "file_id",
    "name",
    "path",
    "mime_type",
    "extension",
    "size_bytes",
    "created_time",
    "modified_time",
    "content_hash",
    "duplicate_group_id",
    "canonical_file_id",
    "is_canonical",
    "corpus_status",
    "exclusion_reason",
    "sieve_rule_ids",
    "object_hint",
    "department_hint",
    "document_type_hint",
    "sensitivity_hint",
    "lifecycle_hint",
    "needs_review",
    "review_reason",
    "safe_for_content_processing",
    "safe_for_physical_delete_candidate",
    "confidence",
]

CANONICAL_MAP_COLUMNS = [
    "duplicate_group_id",
    "file_id",
    "canonical_file_id",
    "is_canonical",
    "name",
    "path",
    "content_hash",
    "dedup_action",
    "dedup_reason",
]

DEDUP_ACTION_COLUMNS = [
    "duplicate_group_id",
    "file_id",
    "canonical_file_id",
    "dedup_action",
    "dry_run_only",
    "safe_for_physical_delete_candidate",
    "reason",
]

SUMMARY_COLUMNS = ["dimension", "value", "count"]


@dataclass(frozen=True)
class CorpusSieveRule:
    rule_id: str
    status: str
    reason: str
    filename_regex: str = ""
    extensions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CorpusSieveConfig:
    empty_file_max_bytes: int = 0
    near_empty_file_max_bytes: int = 16
    review_unmapped_parent: bool = True
    sensitivity_hold_values: set[str] = field(default_factory=set)
    legal_hold_cleanup_categories: set[str] = field(default_factory=set)
    hr_markers: set[str] = field(default_factory=set)
    system_trash_rules: List[CorpusSieveRule] = field(default_factory=list)
    extension_rules: List[CorpusSieveRule] = field(default_factory=list)


@dataclass
class CorpusSieveResult:
    rows: List[Dict[str, Any]]
    canonical_rows: List[Dict[str, Any]]
    excluded_rows: List[Dict[str, Any]]
    review_rows: List[Dict[str, Any]]
    canonical_map_rows: List[Dict[str, Any]]
    dedup_action_rows: List[Dict[str, Any]]
    summary_rows: List[Dict[str, Any]]
    manifest_rows: List[Dict[str, Any]]
    metrics: Dict[str, Any]


def run_corpus_sieve(inventory_path: str | Path, rules_path: str | Path, out_dir: str | Path) -> CorpusSieveResult:
    inventory = read_csv(inventory_path)
    config = load_corpus_sieve_config(rules_path)
    result = build_corpus_sieve(inventory, config)
    write_corpus_sieve_outputs(result, out_dir)
    return result


def build_corpus_sieve(inventory: List[Dict[str, str]], config: CorpusSieveConfig) -> CorpusSieveResult:
    file_rows = [row for row in inventory if row.get("object_kind", "file") == "file"]
    duplicate_groups = build_exact_duplicate_groups(file_rows)
    canonical_by_group = {group_id: choose_canonical(rows) for group_id, rows in duplicate_groups.items()}
    canonical_by_file: Dict[str, str] = {}
    group_by_file: Dict[str, str] = {}
    for group_id, canonical in canonical_by_group.items():
        canonical_id = canonical.get("file_id", "")
        for row in duplicate_groups[group_id]:
            file_id = row.get("file_id", "")
            canonical_by_file[file_id] = canonical_id
            group_by_file[file_id] = group_id

    output_rows: List[Dict[str, Any]] = []
    canonical_map_rows: List[Dict[str, Any]] = []
    dedup_action_rows: List[Dict[str, Any]] = []
    manifest_rows: List[Dict[str, Any]] = []

    for row in file_rows:
        file_id = row.get("file_id", "")
        group_id = group_by_file.get(file_id, "")
        canonical_id = canonical_by_file.get(file_id) or row.get("canonical_candidate_id", "") or file_id
        is_canonical = file_id == canonical_id
        decision = decide_corpus_status(row, config, group_id=group_id, is_canonical=is_canonical)
        corpus_row = build_corpus_row(row, decision, group_id, canonical_id, is_canonical)
        output_rows.append(corpus_row)
        manifest_rows.append(
            {
                "file_id": file_id,
                "name": row.get("name", ""),
                "corpus_status": corpus_row["corpus_status"],
                "canonical_file_id": canonical_id,
                "dry_run_only": True,
                "safe_for_content_processing": corpus_row["safe_for_content_processing"],
                "safe_for_physical_delete_candidate": corpus_row["safe_for_physical_delete_candidate"],
                "reason": corpus_row["exclusion_reason"] or corpus_row["review_reason"],
            }
        )
        if group_id:
            dedup_action = build_dedup_action(corpus_row)
            canonical_map_rows.append(
                {
                    "duplicate_group_id": group_id,
                    "file_id": file_id,
                    "canonical_file_id": canonical_id,
                    "is_canonical": is_canonical,
                    "name": row.get("name", ""),
                    "path": row.get("full_path", ""),
                    "content_hash": stable_content_key(row),
                    "dedup_action": dedup_action["dedup_action"],
                    "dedup_reason": dedup_action["reason"],
                }
            )
            dedup_action_rows.append(dedup_action)

    canonical_rows = [row for row in output_rows if row["corpus_status"] == "CORPUS_KEEP_CANONICAL"]
    excluded_rows = [
        row
        for row in output_rows
        if row["corpus_status"].startswith("CORPUS_EXCLUDE_") or row["corpus_status"] == "CORPUS_SUPPRESS_EXACT_DUPLICATE"
    ]
    review_rows = [
        row
        for row in output_rows
        if row["needs_review"] == "true" or row["corpus_status"].startswith("CORPUS_HOLD_") or row["corpus_status"] == "CORPUS_REVIEW_UNKNOWN_VALUE"
    ]
    summary_rows = build_summary_rows(output_rows)
    metrics = build_metrics(output_rows, duplicate_groups)

    return CorpusSieveResult(
        rows=output_rows,
        canonical_rows=canonical_rows,
        excluded_rows=excluded_rows,
        review_rows=review_rows,
        canonical_map_rows=canonical_map_rows,
        dedup_action_rows=dedup_action_rows,
        summary_rows=summary_rows,
        manifest_rows=manifest_rows,
        metrics=metrics,
    )


def decide_corpus_status(row: Dict[str, str], config: CorpusSieveConfig, group_id: str, is_canonical: bool) -> Dict[str, Any]:
    if group_id and not is_canonical:
        hold_status = duplicate_hold_status(row, config)
        if hold_status:
            return decision(hold_status, "Exact duplicate held by sensitivity/legal/HR gate.", ["corpus_exact_duplicate_hold"], True, False, False, "high")
        return decision(
            "CORPUS_SUPPRESS_EXACT_DUPLICATE",
            "Exact duplicate suppressed from expensive downstream processing.",
            ["corpus_exact_duplicate"],
            False,
            False,
            True,
            "high",
        )

    rule_decision = apply_config_rules(row, config)
    if rule_decision:
        return rule_decision

    if is_empty_or_near_empty(row, config):
        return decision(
            "CORPUS_EXCLUDE_EMPTY",
            "Zero-byte or near-empty file is not useful for content extraction.",
            ["corpus_empty_or_near_empty"],
            False,
            False,
            True,
            "medium",
        )

    if config.review_unmapped_parent and not row.get("full_path", ""):
        return decision(
            "CORPUS_REVIEW_UNKNOWN_VALUE",
            "Missing path/full_path; parent context is incomplete.",
            ["corpus_missing_path_review"],
            True,
            False,
            False,
            "medium",
        )

    if duplicate_hold_status(row, config):
        return decision(
            duplicate_hold_status(row, config) or "CORPUS_HOLD_SENSITIVE",
            "Sensitive/legal/HR file held from automatic downstream processing until policy review.",
            ["corpus_sensitive_hold"],
            True,
            False,
            False,
            "medium",
        )

    return decision("CORPUS_KEEP_CANONICAL", "", ["corpus_keep_default"], False, True, False, "medium")


def apply_config_rules(row: Dict[str, str], config: CorpusSieveConfig) -> Optional[Dict[str, Any]]:
    name = row.get("name", "")
    extension = row.get("extension", "").lower().lstrip(".")
    for rule in config.system_trash_rules:
        if rule.filename_regex and re.search(rule.filename_regex, name):
            return decision(rule.status, rule.reason, [rule.rule_id], needs_review=rule.status.startswith("CORPUS_HOLD_"), safe_for_content=False, safe_for_delete=True, confidence="high")
    for rule in config.extension_rules:
        if extension and extension in rule.extensions:
            needs_review = rule.status.startswith("CORPUS_HOLD_") or rule.status == "CORPUS_REVIEW_UNKNOWN_VALUE"
            safe_for_delete = rule.status.startswith("CORPUS_EXCLUDE_") and not sensitive_family(row, config)
            return decision(rule.status, rule.reason, [rule.rule_id], needs_review, False, safe_for_delete, "high")
    if row.get("cleanup_category") == "system_trash_candidate":
        return decision("CORPUS_EXCLUDE_SYSTEM_TRASH", "Metadata cleanup layer marked system trash.", ["corpus_cleanup_system_trash"], False, False, True, "high")
    return None


def duplicate_hold_status(row: Dict[str, str], config: CorpusSieveConfig) -> str:
    values = {
        row.get("sensitivity_suggestion", ""),
        row.get("cleanup_category", ""),
        row.get("document_family_suggestion", ""),
        row.get("document_type_suggestion", ""),
        row.get("department_suggestion", ""),
        row.get("human_review_queue", ""),
    }
    flat = " ".join(value.lower() for value in values if value)
    if any(marker.lower() in flat for marker in config.hr_markers):
        return "CORPUS_HOLD_HR"
    if row.get("cleanup_category", "") in config.legal_hold_cleanup_categories or "legal" in flat or "contract" in flat:
        return "CORPUS_HOLD_LEGAL"
    if sensitive_family(row, config):
        return "CORPUS_HOLD_SENSITIVE"
    return ""


def sensitive_family(row: Dict[str, str], config: CorpusSieveConfig) -> bool:
    values = {row.get("sensitivity_suggestion", ""), row.get("cleanup_category", "")}
    return bool(values & config.sensitivity_hold_values)


def decision(
    status: str,
    reason: str,
    rule_ids: List[str],
    needs_review: bool,
    safe_for_content: bool,
    safe_for_delete: bool,
    confidence: str,
) -> Dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "rule_ids": rule_ids,
        "needs_review": needs_review,
        "safe_for_content": safe_for_content,
        "safe_for_delete": safe_for_delete,
        "confidence": confidence,
    }


def build_corpus_row(row: Dict[str, str], item_decision: Dict[str, Any], group_id: str, canonical_id: str, is_canonical: bool) -> Dict[str, Any]:
    return {
        "file_id": row.get("file_id", ""),
        "name": row.get("name", ""),
        "path": row.get("full_path", ""),
        "mime_type": row.get("mime_type", ""),
        "extension": row.get("extension", ""),
        "size_bytes": row.get("size", ""),
        "created_time": row.get("created_time", ""),
        "modified_time": row.get("modified_time", ""),
        "content_hash": stable_content_key(row),
        "duplicate_group_id": group_id,
        "canonical_file_id": canonical_id,
        "is_canonical": str(bool(is_canonical)).lower(),
        "corpus_status": item_decision["status"],
        "exclusion_reason": "" if item_decision["status"] == "CORPUS_KEEP_CANONICAL" else item_decision["reason"],
        "sieve_rule_ids": ";".join(item_decision["rule_ids"]),
        "object_hint": row.get("object_suggestion", ""),
        "department_hint": row.get("department_suggestion", ""),
        "document_type_hint": row.get("document_type_suggestion", ""),
        "sensitivity_hint": row.get("sensitivity_suggestion", ""),
        "lifecycle_hint": row.get("lifecycle_status", ""),
        "needs_review": str(bool(item_decision["needs_review"])).lower(),
        "review_reason": item_decision["reason"] if item_decision["needs_review"] else "",
        "safe_for_content_processing": str(bool(item_decision["safe_for_content"])).lower(),
        "safe_for_physical_delete_candidate": str(bool(item_decision["safe_for_delete"])).lower(),
        "confidence": item_decision["confidence"],
    }


def build_dedup_action(corpus_row: Dict[str, Any]) -> Dict[str, Any]:
    status = corpus_row["corpus_status"]
    if corpus_row["is_canonical"] == "true":
        action = "CANONICAL_KEEP"
        reason = "Canonical file selected for exact duplicate group."
    elif status == "CORPUS_HOLD_HR":
        action = "DEDUP_HOLD_HR"
        reason = corpus_row["review_reason"]
    elif status == "CORPUS_HOLD_LEGAL":
        action = "DEDUP_HOLD_LEGAL"
        reason = corpus_row["review_reason"]
    elif status == "CORPUS_HOLD_SENSITIVE":
        action = "DEDUP_HOLD_SENSITIVE"
        reason = corpus_row["review_reason"]
    elif status == "CORPUS_SUPPRESS_EXACT_DUPLICATE":
        action = "EXACT_DUPLICATE_DELETE_CANDIDATE"
        reason = "Dry-run delete candidate; also suppressed from downstream processing."
    else:
        action = "EXACT_DUPLICATE_SUPPRESS_FROM_PROCESSING"
        reason = corpus_row["exclusion_reason"] or "Suppressed from downstream processing."
    return {
        "duplicate_group_id": corpus_row["duplicate_group_id"],
        "file_id": corpus_row["file_id"],
        "canonical_file_id": corpus_row["canonical_file_id"],
        "dedup_action": action,
        "dry_run_only": "true",
        "safe_for_physical_delete_candidate": corpus_row["safe_for_physical_delete_candidate"],
        "reason": reason,
    }


def build_exact_duplicate_groups(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    by_group: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    by_hash: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("duplicate_kind") == "exact" and row.get("duplicate_group_id"):
            by_group[row["duplicate_group_id"]].append(row)
        key = stable_content_key(row)
        if key:
            by_hash[key].append(row)
    groups = {group_id: items for group_id, items in by_group.items() if len(items) > 1}
    next_index = len(groups) + 1
    for key, items in by_hash.items():
        if len(items) < 2:
            continue
        if any(row.get("duplicate_group_id") in groups for row in items):
            continue
        groups[f"EXACT-SIEVE-{next_index:05d}"] = items
        next_index += 1
    return groups


def exact_duplicate_group_id(row: Dict[str, str]) -> str:
    if row.get("duplicate_kind") == "exact":
        return row.get("duplicate_group_id", "")
    key = stable_content_key(row)
    return f"EXACT-HASH-{key}" if key else ""


def stable_content_key(row: Dict[str, str]) -> str:
    if row.get("content_hash"):
        return f"content:{row['content_hash']}"
    if row.get("export_hash"):
        return f"export:{row['export_hash']}"
    if row.get("md5_checksum") and row.get("size"):
        return f"md5:{row['md5_checksum']}:{row['size']}"
    return ""


def choose_canonical(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return sorted(rows, key=canonical_score, reverse=True)[0]


def canonical_score(row: Dict[str, str]) -> tuple:
    path = row.get("full_path", "").lower()
    name = row.get("name", "").lower()
    business_path = not any(marker in path for marker in ["temp", "tmp", "copy", "export", "whatsapp", "telegram", "download"])
    final_signal = any(marker in path or marker in name for marker in ["signed", "final", "contract", "legal", "договор"])
    known_context = sum(1 for field in ["object_suggestion", "department_suggestion", "document_type_suggestion"] if known_value(row.get(field, "")))
    meaningful_name = not any(marker == name or marker in name for marker in ["scan", "image", "copy", "new", "final2"])
    return (
        int(final_signal),
        int(business_path),
        known_context,
        int(meaningful_name),
        int(row.get("size") or 0),
        row.get("modified_time", ""),
        row.get("name", "").lower(),
    )


def known_value(value: str) -> bool:
    lowered = (value or "").strip().lower()
    return bool(lowered and "unknown" not in lowered and "неизвест" not in lowered and "не определ" not in lowered)


def is_empty_or_near_empty(row: Dict[str, str], config: CorpusSieveConfig) -> bool:
    size = row.get("size", "")
    if not str(size).isdigit():
        return False
    return int(size) <= config.empty_file_max_bytes or int(size) <= config.near_empty_file_max_bytes and row.get("extension", "").lower() in {"txt", "csv", "log"}


def build_summary_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    dimensions = {
        "corpus_status": Counter(row["corpus_status"] for row in rows),
        "safe_for_content_processing": Counter(row["safe_for_content_processing"] for row in rows),
        "safe_for_physical_delete_candidate": Counter(row["safe_for_physical_delete_candidate"] for row in rows),
        "sieve_rule_ids": Counter(rule for row in rows for rule in str(row["sieve_rule_ids"]).split(";") if rule),
        "mime_type": Counter(row["mime_type"] for row in rows),
        "extension": Counter(row["extension"] for row in rows),
        "object_hint": Counter(row["object_hint"] for row in rows),
        "department_hint": Counter(row["department_hint"] for row in rows),
        "document_type_hint": Counter(row["document_type_hint"] for row in rows),
    }
    for dimension, counter in dimensions.items():
        for value, count in counter.most_common():
            result.append({"dimension": dimension, "value": value, "count": count})
    return result


def build_metrics(rows: List[Dict[str, Any]], duplicate_groups: Dict[str, List[Dict[str, str]]]) -> Dict[str, Any]:
    statuses = Counter(row["corpus_status"] for row in rows)
    total_files = len(rows)
    safe_for_content = sum(1 for row in rows if row["safe_for_content_processing"] == "true")
    suppressed = sum(
        1
        for row in rows
        if row["duplicate_group_id"] and row["is_canonical"] == "false" and row["safe_for_content_processing"] == "false"
    )
    excluded = sum(count for status, count in statuses.items() if status.startswith("CORPUS_EXCLUDE_"))
    holds = sum(count for status, count in statuses.items() if status.startswith("CORPUS_HOLD_"))
    return {
        "total_files_considered": total_files,
        "canonical_keep": statuses.get("CORPUS_KEEP_CANONICAL", 0),
        "exact_duplicate_groups": len(duplicate_groups),
        "exact_duplicate_files_suppressed": suppressed,
        "excluded_files": excluded,
        "hold_files": holds,
        "review_queue": sum(1 for row in rows if row["needs_review"] == "true"),
        "safe_for_content_processing": safe_for_content,
        "estimated_processing_load_reduction_files": total_files - safe_for_content,
        "estimated_processing_load_reduction_percent": round(((total_files - safe_for_content) / total_files * 100), 2) if total_files else 0,
        "system_trash_excluded": statuses.get("CORPUS_EXCLUDE_SYSTEM_TRASH", 0),
        "temp_cache_excluded": statuses.get("CORPUS_EXCLUDE_TEMP", 0) + statuses.get("CORPUS_EXCLUDE_CACHE_PREVIEW", 0),
        "installers_binaries_excluded": statuses.get("CORPUS_EXCLUDE_INSTALLER", 0) + statuses.get("CORPUS_EXCLUDE_APP_BINARY", 0),
        "mail_archives_excluded": statuses.get("CORPUS_EXCLUDE_MAIL_ARCHIVE", 0),
        "archive_containers_held": statuses.get("CORPUS_HOLD_ARCHIVE_CONTAINER", 0),
        "errors": statuses.get("CORPUS_ERROR", 0),
    }


def write_corpus_sieve_outputs(result: CorpusSieveResult, out_dir: str | Path) -> None:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "corpus_sieve_inventory.csv", CORPUS_COLUMNS, result.rows)
    write_csv(output / "corpus_keep_canonical.csv", CORPUS_COLUMNS, result.canonical_rows)
    write_csv(output / "corpus_excluded.csv", CORPUS_COLUMNS, result.excluded_rows)
    write_csv(output / "corpus_review_queue.csv", CORPUS_COLUMNS, result.review_rows)
    write_csv(output / "dedup_exact_canonical_map.csv", CANONICAL_MAP_COLUMNS, result.canonical_map_rows)
    write_csv(output / "dedup_exact_actions_dry_run.csv", DEDUP_ACTION_COLUMNS, result.dedup_action_rows)
    write_csv(output / "corpus_sieve_summary_by_reason.csv", SUMMARY_COLUMNS, result.summary_rows)
    with (output / "corpus_sieve_manifest.jsonl").open("w", encoding="utf-8") as fh:
        for row in result.manifest_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "corpus_sieve_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(result.metrics, fh, ensure_ascii=False, indent=2)
    write_report(output / "corpus_sieve_report.md", result)


def write_report(path: Path, result: CorpusSieveResult) -> None:
    lines = [
        "# Corpus Sieve Report",
        "",
        "Dry-run only. No Drive files were deleted, moved, renamed, unpacked, OCR-processed or sent to Cloud AI.",
        "",
        "## Metrics",
        "",
    ]
    for key, value in result.metrics.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Status Summary", ""])
    status_counts = Counter(row["corpus_status"] for row in result.rows)
    for status, count in status_counts.most_common():
        lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- corpus_sieve_inventory.csv",
            "- corpus_keep_canonical.csv",
            "- corpus_excluded.csv",
            "- corpus_review_queue.csv",
            "- dedup_exact_canonical_map.csv",
            "- dedup_exact_actions_dry_run.csv",
            "- corpus_sieve_summary_by_reason.csv",
            "- corpus_sieve_manifest.jsonl",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_csv(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, columns: List[str], rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_corpus_sieve_config(path: str | Path) -> CorpusSieveConfig:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    root = data.get("corpus_sieve", data)
    return CorpusSieveConfig(
        empty_file_max_bytes=int(root.get("empty_file_max_bytes", 0)),
        near_empty_file_max_bytes=int(root.get("near_empty_file_max_bytes", 16)),
        review_unmapped_parent=bool(root.get("review_unmapped_parent", True)),
        sensitivity_hold_values=set(root.get("sensitivity_hold_values", [])),
        legal_hold_cleanup_categories=set(root.get("legal_hold_cleanup_categories", [])),
        hr_markers=set(root.get("hr_markers", [])),
        system_trash_rules=[parse_rule(rule) for rule in root.get("system_trash_rules", [])],
        extension_rules=[parse_rule(rule) for rule in root.get("extension_rules", [])],
    )


def parse_rule(rule: Dict[str, Any]) -> CorpusSieveRule:
    return CorpusSieveRule(
        rule_id=str(rule.get("rule_id", "")),
        status=str(rule.get("status", "CORPUS_REVIEW_UNKNOWN_VALUE")),
        reason=str(rule.get("reason", "")),
        filename_regex=str(rule.get("filename_regex", "")),
        extensions=[str(ext).lower().lstrip(".") for ext in rule.get("extensions", [])],
    )
