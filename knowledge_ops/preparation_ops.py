from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from googleapiclient.errors import HttpError

from knowledge_ops.native_drive_ops import (
    AUTO_SAFE_ACTIONS,
    FOLDER_MIME,
    MAIN_HEADERS,
    KnowledgeOps,
    build_services,
    load_config,
    normalize,
    now,
)

ROOT_SCAN_TERMS = [
    "ARTSTUDIO",
    "artstudio",
    "\u0410\u0420\u0422\u0421\u0422\u0423\u0414\u0418\u041e",
    "\u041d\u0435\u0432\u0441\u043a\u0438\u0439",
    "Nevsky",
    "\u041c\u043e\u0441\u043a\u043e\u0432\u0441\u043a\u0438\u0439",
    "Moskovsky",
    "M103",
    "RBI PM",
    "SOP",
]

PREPARATION_HEADERS = [
    "Finding ID",
    "Name",
    "Object ID",
    "Object type",
    "Current parents",
    "Recommended action",
    "Target location",
    "Risk",
    "Reason",
    "Status",
    "Checked at",
]

FOLDER_AUDIT_HEADERS = [
    "Folder name",
    "Folder ID",
    "Canonical ID",
    "Child count",
    "Duplicate status",
    "Recommended action",
    "Execution status",
    "Execution log",
    "Checked at",
]


class PreparationOps(KnowledgeOps):
    def prepare_and_plan(self) -> Dict[str, Any]:
        self.prepare_structure()
        duplicate_results = self.merge_duplicate_root_folders()
        planned = self.plan_reorganization(write_main=True)
        validation = self.validate_readiness()
        manual = self.manual_results(duplicate_results)
        return {
            "duplicateFoldersProcessed": len(duplicate_results),
            "manualActionsRequired": manual,
            "plannedActions": planned["plannedActions"],
            "validation": validation,
        }

    def complete_preparation(self) -> Dict[str, Any]:
        self.prepare_structure()
        duplicate_results = self.merge_duplicate_root_folders()
        plan = self.plan_reorganization(write_main=True)
        execution = self.execute_safe_actions()
        validation = self.validate_readiness()
        manual = self.manual_results(duplicate_results)
        status = "completed with manual actions" if manual or validation.get("missingFolders") else "completed"
        self.append_tool_run(
            task="Complete ARTSTUDIO preparation stage",
            output=(
                f"Duplicate folders processed: {len(duplicate_results)}; "
                f"manual actions required: {len(manual)}; "
                f"planned actions: {plan['plannedActions']}; executed rows: {execution['processed']}"
            ),
            status=status,
            review_required="yes" if manual or validation.get("missingFolders") else "no",
            notes="Preparation stage uses GitHub-native Drive operations; trash failures fall back to pending-trash quarantine.",
        )
        return {
            "duplicateFoldersProcessed": len(duplicate_results),
            "manualActionsRequired": manual,
            "plannedActions": plan["plannedActions"],
            "executedRows": execution["processed"],
            "validation": validation,
        }

    def plan_reorganization(self, write_main: bool = True) -> Dict[str, Any]:
        findings: List[List[str]] = []
        main_rows: List[List[str]] = []
        seen_action_keys = self.existing_action_keys()
        candidates = self.discover_candidates()
        folder_ids = {folder["name"]: self.resolve_folder_path("ARTSTUDIO/" + folder["name"]) for folder in self.config["drive"]["folders"]}
        folder_ids["98_Project_Methodology"] = self.resolve_folder_path("ARTSTUDIO/00_CONTROL_CENTER/98_Project_Methodology")
        folder_ids["99_Setup_Archive"] = self.resolve_folder_path("ARTSTUDIO/00_CONTROL_CENTER/99_Setup_Archive")
        canonical_folder_names = {folder["name"] for folder in self.config["drive"]["folders"]}

        for file_obj in candidates:
            name = file_obj.get("name", "")
            object_id = file_obj.get("id", "")
            mime_type = file_obj.get("mimeType", "")
            if object_id in {self.artstudio_folder_id, self.control_center_folder_id}:
                continue
            if mime_type == FOLDER_MIME and name in canonical_folder_names:
                continue
            target_location, reason, risk = self.classify_target(name, mime_type)
            if not target_location:
                findings.append([
                    self.finding_id("REVIEW", object_id),
                    name,
                    object_id,
                    mime_type,
                    ",".join(file_obj.get("parents", [])),
                    "human review required",
                    "",
                    "medium",
                    "No confident target section from naming rules.",
                    "needs_review",
                    now(),
                ])
                continue
            target_id = folder_ids.get(target_location.split("/")[-1])
            parents = file_obj.get("parents", [])
            already_in_target = target_id in parents if target_id else False
            action = "move file" if mime_type != FOLDER_MIME else "move folder"
            action_key = f"{object_id}:{action}:{target_location}"
            status = "already_in_target" if already_in_target else "planned"
            findings.append([
                self.finding_id("PLAN", object_id),
                name,
                object_id,
                "folder" if mime_type == FOLDER_MIME else mime_type,
                ",".join(parents),
                "none" if already_in_target else action,
                "ARTSTUDIO/" + target_location,
                risk,
                reason,
                status,
                now(),
            ])
            if already_in_target or action_key in seen_action_keys:
                continue
            main_rows.append(self.main_action_row(
                action_id=self.finding_id("AUTO", object_id),
                name=name,
                current_location=",".join(parents) or "outside ARTSTUDIO or unknown",
                problem="Project-related file is outside the canonical ARTSTUDIO section.",
                action=action,
                target_location="ARTSTUDIO/" + target_location,
                risk=risk,
                recommendation=reason,
                object_id=object_id,
                object_url=file_obj.get("webViewLink", ""),
                object_type="folder" if mime_type == FOLDER_MIME else mime_type,
                safe_action=action,
            ))
            seen_action_keys.add(action_key)

        reorg_id = self.find_control_spreadsheet("ARTSTUDIO_Reorganization_Plan")
        self.replace_sheet(reorg_id, "Preparation Recommendations", PREPARATION_HEADERS, findings)
        if write_main and main_rows:
            self.append_main_rows(reorg_id, main_rows)
        self.append_tool_run(
            task="Plan ARTSTUDIO Drive reorganization",
            output=f"Prepared {len(findings)} findings and {len(main_rows)} executable plan rows",
            status="completed",
            review_required="yes" if any(row[9] == "needs_review" for row in findings) else "no",
            notes="Planning uses filename-based classification; uncertain files stay in human review.",
        )
        return {"findings": len(findings), "plannedActions": len(main_rows)}

    def merge_duplicate_root_folders(self) -> List[Dict[str, str]]:
        root_folders = self.list_children_detailed(self.artstudio_folder_id, mime_type=FOLDER_MIME)
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for folder in root_folders:
            grouped[folder["name"]].append(folder)

        audit_rows: List[List[str]] = []
        results: List[Dict[str, str]] = []
        for name, folders in sorted(grouped.items()):
            canonical = self.choose_canonical_folder(name, folders)
            for folder in folders:
                child_count = self.count_children(folder["id"])
                is_duplicate = folder["id"] != canonical["id"]
                recommended = "move children to canonical and trash empty duplicate" if is_duplicate else "keep canonical"
                result = {"status": "canonical", "message": "Canonical folder kept."}
                if is_duplicate:
                    result = self.merge_duplicate_folder(folder, canonical)
                    results.append(result)
                audit_rows.append([
                    name,
                    folder["id"],
                    canonical["id"],
                    str(child_count),
                    "duplicate" if is_duplicate else "canonical",
                    recommended,
                    result["status"],
                    result["message"],
                    now(),
                ])

        manual = self.manual_results(results)
        reorg_id = self.find_control_spreadsheet("ARTSTUDIO_Reorganization_Plan")
        self.replace_sheet(reorg_id, "Folder Duplicate Audit", FOLDER_AUDIT_HEADERS, audit_rows)
        self.append_tool_run(
            task="Merge duplicate ARTSTUDIO root folders",
            output=f"Processed {len(results)} duplicate root folders; manual actions required: {len(manual)}",
            status="completed with manual actions" if manual else "completed",
            review_required="yes" if manual else "no",
            notes="Duplicate folders are trashed only after their children are moved or when already empty. Trash failures fall back to pending-trash quarantine.",
        )
        return results

    def merge_duplicate_folder(self, duplicate: Dict[str, Any], canonical: Dict[str, Any]) -> Dict[str, str]:
        children = self.list_children_detailed(duplicate["id"])
        moved = 0
        move_errors: List[str] = []
        for child in children:
            if self.dry_run:
                moved += 1
                continue
            try:
                self.move_file(child["id"], canonical["id"], child.get("parents", [duplicate["id"]]))
                moved += 1
            except HttpError as exc:
                move_errors.append(f"{child.get('name')} ({child.get('id')}): {self.http_error_message(exc)}")
        if move_errors:
            return {
                "status": "manual_owner_action_required",
                "message": (
                    f"Could not move all children from duplicate folder {duplicate['name']} ({duplicate['id']}) "
                    f"to canonical {canonical['id']}. Errors: " + "; ".join(move_errors[:5])
                ),
            }
        if not self.dry_run:
            try:
                self.services.drive.files().update(
                    fileId=duplicate["id"],
                    body={"trashed": True},
                    supportsAllDrives=True,
                ).execute()
            except HttpError as exc:
                quarantine = self.quarantine_pending_trash(
                    object_id=duplicate["id"],
                    reason=(
                        f"Moved {moved} children into canonical folder {canonical['id']}, "
                        f"but Drive trash failed: {self.http_error_message(exc)}"
                    ),
                )
                if quarantine["status"] == "quarantined_pending_trash":
                    return quarantine
                return {
                    "status": "manual_owner_action_required",
                    "message": (
                        f"Moved {moved} children into canonical folder {canonical['id']}, but could not trash "
                        f"or quarantine duplicate folder {duplicate['name']} ({duplicate['id']}). "
                        f"{quarantine['message']}"
                    ),
                }
        return {
            "status": "completed",
            "message": f"Merged duplicate folder {duplicate['name']} ({duplicate['id']}) into {canonical['id']}; moved {moved}; trashed duplicate",
        }

    def choose_canonical_folder(self, name: str, folders: List[Dict[str, Any]]) -> Dict[str, Any]:
        if name == "00_CONTROL_CENTER":
            for folder in folders:
                if folder["id"] == self.control_center_folder_id:
                    return folder
        scored: List[Tuple[int, str, Dict[str, Any]]] = []
        for folder in folders:
            child_count = self.count_children(folder["id"])
            created = folder.get("createdTime", "")
            scored.append((child_count, created, folder))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return scored[0][2]

    def discover_candidates(self) -> List[Dict[str, Any]]:
        candidates: Dict[str, Dict[str, Any]] = {}
        for term in ROOT_SCAN_TERMS:
            for file_obj in self.search_drive_by_name(term):
                candidates[file_obj["id"]] = file_obj
        for item in self.list_children_detailed(self.artstudio_folder_id):
            candidates[item["id"]] = item
        return list(candidates.values())

    def classify_target(self, name: str, mime_type: str) -> Tuple[Optional[str], str, str]:
        lower = name.lower()
        if name.startswith("ARTSTUDIO_"):
            return "00_CONTROL_CENTER", "Canonical ARTSTUDIO control file.", "low"
        if "control_center" in lower or "bootstrap" in lower or mime_type == "application/vnd.google-apps.script":
            return "00_CONTROL_CENTER/99_Setup_Archive", "Legacy setup/control-center artifact.", "low"
        if name.startswith("ARTSTUDIO Base"):
            return "00_CONTROL_CENTER/98_Project_Methodology", "Stage 0 methodology/base artifact.", "low"
        if any(token in lower for token in ["brand", "\u0431\u0440\u0435\u043d\u0434", "art_for_apart", "00_artstudio", "rbi pm"]):
            return "02_Brand_Context", "Brand or positioning material.", "low"
        if any(token in lower for token in ["\u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435", "\u043d\u043e\u043c\u0435\u0440\u043d\u043e\u0433\u043e \u0444\u043e\u043d\u0434\u0430", "\u043a\u043b\u0430\u0441\u0441\u0438\u0444\u0438\u043a\u0430", "\u043a\u043e\u043d\u0434\u0438\u0446\u0438\u043e\u043d\u0435\u0440", "\u043a\u043e\u0442\u0451\u043b", "\u043a\u043e\u0442\u0435\u043b", "\u0441\u0447\u0451\u0442\u0447\u0438\u043a", "\u0441\u0447\u0435\u0442\u0447\u0438\u043a"]):
            return "03_Object_Data", "Object/property factual material.", "low"
        if any(token in lower for token in ["sop", "\u0441\u0442\u0430\u043d\u0434\u0430\u0440\u0442", "\u043f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0430", "\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u043e\u043d\u043d\u0430\u044f", "\u044e\u043a\u0430\u0441\u0441", "\u0437\u0430\u0435\u0437\u0434", "\u0432\u044b\u0441\u0435\u043b", "\u0436\u0430\u043b\u043e\u0431", "\u043f\u0440\u043e\u0436\u0438\u0432", "faq", "\u0447\u0430\u0441\u0442\u044b\u0435", "\u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f", "\u043c\u0430\u0440\u0448\u0440\u0443\u0442", "\u043f\u0430\u043c\u044f\u0442\u043a\u0430"]):
            return "04_Standards_SOP", "Operational standard, SOP, instruction or template.", "low"
        if mime_type == "text/html" or any(token in lower for token in ["\u043e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u044b\u0439 \u0441\u0430\u0439\u0442", "\u0441\u0430\u0439\u0442", "e-book", "\u043a\u043d\u0438\u0433\u0430 \u0433\u043e\u0441\u0442\u044f", "guest book", "\u0438\u043d\u0442\u0435\u0440\u043d\u0435\u0442-\u043c\u0430\u0433\u0430\u0437\u0438\u043d"]):
            return "05_Official_Sites", "Guest-facing web/site/e-book material.", "low"
        if any(token in lower for token in ["ota", "travel", "\u044d\u043a\u0441\u0442\u0440\u0430\u043d\u0435\u0442", "\u044d\u043a\u0441\u0442\u0440\u0430\u043d\u0435\u0442\u043e\u0432"]):
            return "06_OTA", "OTA or extranet material.", "low"
        if any(token in lower for token in ["review", "\u043e\u0442\u0437\u044b\u0432", "feedback"]):
            return "07_Reviews", "Review or guest feedback material.", "low"
        if any(token in lower for token in ["\u0434\u043e\u0433\u043e\u0432\u043e\u0440", "legal", "\u044e\u0440\u0438\u0434", "\u0432\u044b\u043f\u0438\u0441\u043a\u0430", "\u043f\u0435\u0447\u0430\u0442\u044c", "\u043f\u043e\u0434\u043f\u0438\u0441\u044c"]):
            return "08_Legal_Files", "Legal or formal document.", "medium"
        if any(token in lower for token in ["\u0441\u043e\u0431\u0441\u0442\u0432\u0435\u043d", "owner", "investor", "\u0438\u043d\u0432\u0435\u0441\u0442", "\u043c\u043e\u0442\u0438\u0432\u0430\u0446", "\u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u0447\u0435\u0441\u0442\u0432"]):
            return "09_Owner_Investor", "Owner/investor material.", "low"
        if any(token in lower for token in ["competitor", "\u043a\u043e\u043d\u043a\u0443\u0440", "market", "\u0440\u044b\u043d\u043e\u043a"]):
            return "10_Competitors_Market", "Competitor or market context.", "low"
        return None, "No matching rule.", "medium"

    def list_children_detailed(self, parent_id: str, mime_type: Optional[str] = None) -> List[Dict[str, Any]]:
        query = [f"'{parent_id}' in parents", "trashed = false"]
        if mime_type:
            query.append(f"mimeType = '{mime_type}'")
        response = self.services.drive.files().list(
            q=" and ".join(query),
            fields="files(id,name,mimeType,parents,webViewLink,modifiedTime,createdTime,size)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return response.get("files", [])

    def search_drive_by_name(self, term: str) -> List[Dict[str, Any]]:
        safe = term.replace("'", "\\'")
        response = self.services.drive.files().list(
            q=f"name contains '{safe}' and trashed = false",
            fields="files(id,name,mimeType,parents,webViewLink,modifiedTime,createdTime,size)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return response.get("files", [])

    def count_children(self, folder_id: str) -> int:
        response = self.services.drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return len(response.get("files", []))

    def move_file(self, object_id: str, target_parent: str, previous_parents: List[str]) -> None:
        self.services.drive.files().update(
            fileId=object_id,
            addParents=target_parent,
            removeParents=",".join(previous_parents),
            fields="id, parents",
            supportsAllDrives=True,
        ).execute()

    def append_main_rows(self, spreadsheet_id: str, rows: List[List[str]]) -> None:
        if self.dry_run:
            return
        self.services.sheets.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="'Main'!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    def existing_action_keys(self) -> set[str]:
        try:
            spreadsheet_id = self.find_control_spreadsheet("ARTSTUDIO_Reorganization_Plan")
            values = self.get_sheet_values(spreadsheet_id, "Main")
            if not values:
                return set()
            headers = values[0]
            keys = set()
            for row in values[1:]:
                item = self.row_to_item(headers, row)
                object_id = item.get("Object ID", "")
                action = normalize(item.get("Safe action") or item.get("Recommended action"))
                target = item.get("Target location", "")
                if object_id and action and target:
                    keys.add(f"{object_id}:{action}:{target}")
            return keys
        except Exception as exc:
            print(f"Existing plan scan skipped: {exc}", file=sys.stderr)
            return set()

    def main_action_row(
        self,
        action_id: str,
        name: str,
        current_location: str,
        problem: str,
        action: str,
        target_location: str,
        risk: str,
        recommendation: str,
        object_id: str,
        object_url: str,
        object_type: str,
        safe_action: str,
    ) -> List[str]:
        row_by_header = {
            "Action ID": action_id,
            "Current file / folder": name,
            "Current location": current_location,
            "Problem": problem,
            "Recommended action": action,
            "Target name": name,
            "Target location": target_location,
            "Priority": "high",
            "Risk": risk,
            "Machine recommendation": recommendation,
            "Human decision": "auto-safe" if safe_action in AUTO_SAFE_ACTIONS else "human review required",
            "Execution status": "planned",
            "Executed by": "",
            "Date": now(),
            "Object ID": object_id,
            "Object URL": object_url,
            "Object type": object_type,
            "Canonical object ID": "",
            "Canonical object URL": "",
            "Detection rule": "preparation filename classification",
            "Compare result": "not a duplicate check",
            "Unique content risk": "none detected for move-only action",
            "Safe action": safe_action,
            "Execution log": "",
            "Last checked": now(),
        }
        return [row_by_header.get(header, "") for header in MAIN_HEADERS]

    @staticmethod
    def manual_results(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        return [item for item in results if item.get("status") not in {"completed", "canonical", "quarantined_pending_trash"}]

    @staticmethod
    def http_error_message(exc: HttpError) -> str:
        try:
            data = json.loads(exc.content.decode("utf-8"))
            return data.get("error", {}).get("message") or str(exc)
        except Exception:
            return str(exc)

    @staticmethod
    def finding_id(prefix: str, object_id: str) -> str:
        suffix = object_id[-8:] if object_id else datetime.now(timezone.utc).strftime("%H%M%S")
        return f"GHA-{prefix}-{suffix}"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="ARTSTUDIO preparation-stage operations")
    parser.add_argument("command", choices=["plan-reorganization", "prepare-and-plan", "complete-prep"])
    parser.add_argument("--config", default="config/control-center.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    ops = PreparationOps(config=config, services=build_services(), dry_run=args.dry_run)
    if args.command == "plan-reorganization":
        result = ops.plan_reorganization(write_main=True)
    elif args.command == "prepare-and-plan":
        result = ops.prepare_and_plan()
    elif args.command == "complete-prep":
        result = ops.complete_preparation()
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
