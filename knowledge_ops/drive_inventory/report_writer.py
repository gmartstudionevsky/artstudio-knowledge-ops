from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from knowledge_ops.drive_inventory.models import INVENTORY_COLUMNS, DriveInventoryItem
from knowledge_ops.drive_inventory.path_analyzer import folder_statistics
from knowledge_ops.drive_inventory.scanner import InventoryResult

FOLDER_COLUMNS = ["file_id", "name", "full_path", "depth", "file_count", "subfolder_count", "top_mime_types", "chaos_signals"]
ERROR_COLUMNS = ["file_id", "name", "error"]
MIGRATION_COLUMNS = [
    "file_id",
    "current_path",
    "name",
    "suggested_object",
    "suggested_department",
    "suggested_document_type",
    "suggested_process",
    "sensitivity",
    "duplicate_group_id",
    "duplicate_kind",
    "canonical_candidate_id",
    "preliminary_action",
    "confidence",
    "reason",
    "human_decision",
    "future_target_area",
    "final_location",
    "approved_by",
    "approved_at",
    "execution_status",
]


def write_reports(result: InventoryResult, out_dir: str | Path) -> None:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    items = [item for item in result.items if not item.is_google_sheet_skipped]
    folders = folder_statistics(result.items)
    exact = [item for item in items if item.duplicate_kind == "exact"]
    version = [item for item in items if item.duplicate_kind == "version_candidate"]
    semantic = [item for item in items if item.duplicate_kind == "semantic_candidate"]
    classification_review = [item for item in items if item.confidence in {"low", "medium"} or item.document_type_suggestion == "неизвестно"]
    sensitivity_review = [item for item in items if item.action_recommendation == "SENSITIVE_REVIEW_REQUIRED"]
    migration_rows = build_migration_plan(items)

    write_csv(output / "inventory.csv", INVENTORY_COLUMNS, (item.to_row() for item in items))
    write_csv(output / "folders.csv", FOLDER_COLUMNS, folders)
    write_csv(output / "skipped_google_sheets.csv", INVENTORY_COLUMNS, (item.to_row() for item in result.skipped_google_sheets))
    write_csv(output / "exact_duplicates.csv", INVENTORY_COLUMNS, (item.to_row() for item in exact))
    write_csv(output / "version_duplicate_candidates.csv", INVENTORY_COLUMNS, (item.to_row() for item in version))
    write_csv(output / "semantic_duplicate_candidates.csv", INVENTORY_COLUMNS, (item.to_row() for item in semantic))
    write_csv(output / "classification_review.csv", INVENTORY_COLUMNS, (item.to_row() for item in classification_review))
    write_csv(output / "sensitivity_review.csv", INVENTORY_COLUMNS, (item.to_row() for item in sensitivity_review))
    write_csv(output / "migration_decision_plan.csv", MIGRATION_COLUMNS, migration_rows)
    write_csv(output / "errors.csv", ERROR_COLUMNS, result.errors)
    write_tree(output / "drive_structure_tree.md", folders)
    write_audit_report(output / "audit_report.md", result, folders, exact, version, semantic, sensitivity_review)
    write_excel(
        output / "inventory.xlsx",
        result,
        items,
        folders,
        exact,
        version,
        semantic,
        classification_review,
        sensitivity_review,
        migration_rows,
    )


def write_csv(path: Path, columns: List[str], rows: Iterable[Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_migration_plan(items: List[DriveInventoryItem]) -> List[Dict[str, str]]:
    rows = []
    for item in items:
        rows.append(
            {
                "file_id": item.file_id,
                "current_path": item.full_path,
                "name": item.name,
                "suggested_object": item.object_suggestion,
                "suggested_department": item.department_suggestion,
                "suggested_document_type": item.document_type_suggestion,
                "suggested_process": item.process_suggestion,
                "sensitivity": item.sensitivity_suggestion,
                "duplicate_group_id": item.duplicate_group_id,
                "duplicate_kind": item.duplicate_kind,
                "canonical_candidate_id": item.canonical_candidate_id,
                "preliminary_action": item.action_recommendation,
                "confidence": item.confidence,
                "reason": item.reason,
                "human_decision": "",
                "future_target_area": future_target_area(item),
                "final_location": "",
                "approved_by": "",
                "approved_at": "",
                "execution_status": "not_planned",
            }
        )
    return rows


def future_target_area(item: DriveInventoryItem) -> str:
    if item.duplicate_group_id:
        return "Карантин дублей"
    if item.document_family_suggestion == "стандарты / SOP / инструкции":
        return "Канон / стандарты / регламенты / SOP"
    if item.document_family_suggestion == "шаблоны и формы":
        return "Шаблоны и бланки"
    if item.sensitivity_suggestion in {"legal_contract"}:
        return "Юридические / обязательные документы"
    if item.sensitivity_suggestion in {"financial", "accounting"}:
        return "Финансы / бухгалтерия"
    if item.sensitivity_suggestion in {"HR", "employee_data"}:
        return "Кадры"
    if item.department_suggestion == "маркетинг / SMM / бренд":
        return "Маркетинг и медиа"
    if item.document_family_suggestion == "отчёты / реестры / финансы":
        return "Отчёты и аналитика"
    if item.object_suggestion not in {"объект не определён", "не объектный / общий документ"}:
        return "Объектные материалы"
    if item.department_suggestion != "не определено":
        return "Подразделение"
    return "Не определено"


def write_tree(path: Path, folders: List[Dict[str, str]]) -> None:
    lines = ["# Drive structure tree", ""]
    for row in folders:
        indent = "  " * max(0, int(row["depth"]))
        lines.append(
            f"{indent}- {row['name']} | files={row['file_count']} | folders={row['subfolder_count']} | "
            f"depth={row['depth']} | types={row['top_mime_types'] or 'n/a'} | signals={row['chaos_signals'] or 'none'}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_audit_report(
    path: Path,
    result: InventoryResult,
    folders: List[Dict[str, str]],
    exact: List[DriveInventoryItem],
    version: List[DriveInventoryItem],
    semantic: List[DriveInventoryItem],
    sensitivity: List[DriveInventoryItem],
) -> None:
    items = [item for item in result.items if not item.is_google_sheet_skipped]
    files = [item for item in items if item.object_kind == "file"]
    lines = [
        "# Drive inventory audit report",
        "",
        f"- Run started: {result.started_at}",
        f"- Drive scope: {result.scope}",
        f"- Mode: {result.mode}",
        f"- Total objects listed: {len(result.items)}",
        f"- Folders: {len([item for item in result.items if item.object_kind == 'folder'])}",
        f"- Files inventoried: {len(files)}",
        f"- Google Sheets skipped: {len(result.skipped_google_sheets)}",
        "",
        "## Distributions",
        counter_section("Mime types", Counter(item.mime_type for item in files)),
        counter_section("Extensions", Counter(item.extension or "(none)" for item in files)),
        counter_section("Objects", Counter(item.object_suggestion for item in files)),
        counter_section("Departments", Counter(item.department_suggestion for item in files)),
        counter_section("Document types", Counter(item.document_type_suggestion for item in files)),
        counter_section("Sensitivity", Counter(item.sensitivity_suggestion for item in files)),
        "",
        "## Folder hotspots",
    ]
    for row in sorted(folders, key=lambda item: int(item["file_count"]), reverse=True)[:20]:
        lines.append(f"- {row['full_path']}: files={row['file_count']}, folders={row['subfolder_count']}, signals={row['chaos_signals'] or 'none'}")
    lines.extend(
        [
            "",
            "## Duplicate and review queues",
            f"- Exact duplicate rows: {len(exact)}; groups: {count_groups(exact)}",
            f"- Version candidate rows: {len(version)}; groups: {count_groups(version)}",
            f"- Semantic candidate rows: {len(semantic)}; groups: {count_groups(semantic)}",
            f"- Potentially sensitive rows: {len(sensitivity)}",
            f"- Unknown document type rows: {sum(1 for item in files if item.document_type_suggestion == 'неизвестно')}",
            "",
            "## Errors and limitations",
            f"- Errors: {len(result.errors)}",
        ]
    )
    for limitation in result.limitations or ["No destructive Drive operations are implemented in this inventory contour."]:
        lines.append(f"- {limitation}")
    lines.extend(
        [
            "",
            "## Next stage recommendations",
            "- Review sensitivity_review.csv before any migration decision.",
            "- Validate exact duplicate groups manually; do not delete in this stage.",
            "- Use migration_decision_plan.csv as a decision table, not as an execution plan.",
            "- Run the first real audit with max-files 100, then review output before full inventory.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def counter_section(title: str, counter: Counter) -> str:
    rows = "; ".join(f"{key}={value}" for key, value in counter.most_common(20))
    return f"- {title}: {rows or 'n/a'}"


def count_groups(items: List[DriveInventoryItem]) -> int:
    return len({item.duplicate_group_id for item in items if item.duplicate_group_id})


def write_excel(
    path: Path,
    result: InventoryResult,
    items: List[DriveInventoryItem],
    folders: List[Dict[str, str]],
    exact: List[DriveInventoryItem],
    version: List[DriveInventoryItem],
    semantic: List[DriveInventoryItem],
    classification_review: List[DriveInventoryItem],
    sensitivity_review: List[DriveInventoryItem],
    migration_rows: List[Dict[str, str]],
) -> None:
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    add_rows(
        summary,
        ["Metric", "Value"],
        [
            {"Metric": "Run started", "Value": result.started_at},
            {"Metric": "Scope", "Value": result.scope},
            {"Metric": "Mode", "Value": result.mode},
            {"Metric": "Total listed", "Value": len(result.items)},
            {"Metric": "Files inventoried", "Value": len(items)},
            {"Metric": "Folders", "Value": len([item for item in result.items if item.object_kind == "folder"])},
            {"Metric": "Skipped Google Sheets", "Value": len(result.skipped_google_sheets)},
            {"Metric": "Errors", "Value": len(result.errors)},
        ],
    )
    add_sheet(wb, "Inventory", INVENTORY_COLUMNS, [item.to_row() for item in items])
    add_sheet(wb, "Folders", FOLDER_COLUMNS, folders)
    add_sheet(wb, "Skipped Google Sheets", INVENTORY_COLUMNS, [item.to_row() for item in result.skipped_google_sheets])
    add_sheet(wb, "Exact Duplicates", INVENTORY_COLUMNS, [item.to_row() for item in exact])
    add_sheet(wb, "Version Candidates", INVENTORY_COLUMNS, [item.to_row() for item in version])
    add_sheet(wb, "Semantic Candidates", INVENTORY_COLUMNS, [item.to_row() for item in semantic])
    add_sheet(wb, "Classification Review", INVENTORY_COLUMNS, [item.to_row() for item in classification_review])
    add_sheet(wb, "Sensitivity Review", INVENTORY_COLUMNS, [item.to_row() for item in sensitivity_review])
    add_sheet(wb, "Migration Decision Plan", MIGRATION_COLUMNS, migration_rows)
    add_sheet(wb, "Errors", ERROR_COLUMNS, result.errors)
    wb.save(path)


def add_sheet(wb: Workbook, title: str, columns: List[str], rows: List[Dict[str, object]]) -> None:
    ws = wb.create_sheet(title=title[:31])
    add_rows(ws, columns, rows)


def add_rows(ws, columns: List[str], rows: List[Dict[str, object]]) -> None:
    ws.append(columns)
    header_fill = PatternFill("solid", fgColor="E8EEF7")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    for row in rows:
        ws.append([row.get(column, "") for column in columns])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for idx, column in enumerate(columns, start=1):
        max_len = max([len(str(column))] + [len(str(row.get(column, ""))) for row in rows[:200]])
        ws.column_dimensions[get_column_letter(idx)].width = min(max(max_len + 2, 10), 42)
