from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]

FOLDER_MIME = "application/vnd.google-apps.folder"
SHEETS_MIME = "application/vnd.google-apps.spreadsheet"
PENDING_TRASH_FOLDER_NAME = "00_PENDING_TRASH"

MAIN_HEADERS = [
    "Action ID", "Current file / folder", "Current location", "Problem",
    "Recommended action", "Target name", "Target location", "Priority", "Risk",
    "Machine recommendation", "Human decision", "Execution status", "Executed by",
    "Date", "Object ID", "Object URL", "Object type", "Canonical object ID",
    "Canonical object URL", "Detection rule", "Compare result",
    "Unique content risk", "Safe action", "Execution log", "Last checked",
]

TOOL_RUN_HEADERS = [
    "Run ID", "Date / time", "Tool", "Task", "Input sources", "Output",
    "Affected files", "Status", "Human review required", "Human decision", "Notes",
]

VALIDATION_HEADERS = ["Check ID", "Check name", "Expected", "Actual", "Status", "Notes", "Checked at"]

AUTO_SAFE_ACTIONS = {
    "create folder",
    "move file",
    "move folder",
    "rename file",
    "rename folder",
    "archive setup artifact",
    "move methodology file",
    "trash duplicate",
}

BLOCKING_DECISIONS = {"rejected", "postponed", "needs discussion"}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def optional_env(name: str, fallback: str) -> str:
    """Use an environment override only when GitHub Actions provided a non-empty value."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        return fallback
    return value.strip()


def require_drive_id(label: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise RuntimeError(
            f"{label} is empty. Set it in config/control-center.json or provide a non-empty GitHub secret override."
        )
    if value.startswith("http"):
        raise RuntimeError(f"{label} must be a raw Google Drive folder ID, not a URL: {value}")
    return value


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_service_account_credentials() -> service_account.Credentials:
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    json_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    delegated_user = os.environ.get("GOOGLE_DELEGATED_USER")

    if raw_json:
        info = json.loads(raw_json)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    elif json_path:
        credentials = service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)
    else:
        raise RuntimeError("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS.")

    if delegated_user:
        credentials = credentials.with_subject(delegated_user)
    return credentials


@dataclass
class Services:
    drive: Any
    sheets: Any


class KnowledgeOps:
    def __init__(self, config: Dict[str, Any], services: Services, dry_run: bool = False):
        self.config = config
        self.services = services
        self.dry_run = dry_run
        drive_cfg = config["drive"]
        self.artstudio_folder_id = require_drive_id(
            "ARTSTUDIO folder ID",
            optional_env("ARTSTUDIO_FOLDER_ID", drive_cfg["artstudioFolderId"]),
        )
        self.control_center_folder_id = require_drive_id(
            "CONTROL_CENTER folder ID",
            optional_env("CONTROL_CENTER_FOLDER_ID", drive_cfg["controlCenterFolderId"]),
        )
        self._control_files: Dict[str, str] = {}

    def prepare_structure(self) -> Dict[str, Any]:
        created: List[str] = []
        for folder in self.config["drive"]["folders"]:
            name = folder["name"]
            folder_id, was_created = self.get_or_create_folder(self.artstudio_folder_id, name)
            if was_created:
                created.append(name)
        for folder in self.config["drive"].get("controlCenterSubfolders", []):
            name = folder["name"]
            folder_id, was_created = self.get_or_create_folder(self.control_center_folder_id, name)
            if was_created:
                created.append(f"00_CONTROL_CENTER/{name}")
        self.append_tool_run(
            task="GitHub-native prepare Drive structure",
            output="Created: " + ", ".join(created) if created else "All canonical folders already exist",
            status="completed",
            review_required="no",
            notes="Executed by GitHub Actions service account; no permanent delete or permission changes.",
        )
        return {"created": created}

    def execute_safe_actions(self) -> Dict[str, Any]:
        spreadsheet_id = self.find_control_spreadsheet("ARTSTUDIO_Reorganization_Plan")
        values = self.get_sheet_values(spreadsheet_id, "Main")
        if not values:
            return {"processed": 0, "results": []}
        headers = values[0]
        self.ensure_headers(spreadsheet_id, "Main", headers, MAIN_HEADERS)
        values = self.get_sheet_values(spreadsheet_id, "Main")
        headers = values[0]
        results = []
        for idx, row in enumerate(values[1:], start=2):
            item = self.row_to_item(headers, row)
            if not self.should_execute(item):
                continue
            result = self.execute_row(item)
            self.update_execution_cells(spreadsheet_id, "Main", headers, idx, result)
            results.append(result)
        self.append_tool_run(
            task="GitHub-native execute safe actions",
            output=f"Processed {len(results)} executable rows",
            status=self.execution_run_status(results),
            review_required="yes" if self.execution_needs_review(results) else "no",
            notes="Duplicate deletion uses Drive trash only; permanent delete is disabled.",
        )
        return {"processed": len(results), "results": results}

    def validate_readiness(self) -> Dict[str, Any]:
        root_folders = self.list_children(self.artstudio_folder_id, mime_type=FOLDER_MIME)
        root_names = {item["name"] for item in root_folders}
        expected = {folder["name"] for folder in self.config["drive"]["folders"]}
        missing = sorted(expected - root_names)
        control_files = self.config.get("controlFiles", [])
        found_control = [name for name in control_files if self.find_file_in_folder(self.control_center_folder_id, name)]
        rows = [
            ["VAL-NATIVE-001", "Canonical root folders", "all configured folders exist", ", ".join(missing) if missing else "all present", "WARN" if missing else "PASS", "", now()],
            ["VAL-NATIVE-002", "Control files", str(len(control_files)), str(len(found_control)), "PASS" if len(found_control) == len(control_files) else "WARN", "", now()],
            ["VAL-NATIVE-003", "Runtime", "GitHub Actions native", "GitHub service account runtime", "PASS", "Apps Script is legacy only.", now()],
            ["VAL-NATIVE-004", "Permanent delete policy", "disabled", "disabled", "PASS", "Only Drive trash is allowed for obvious duplicates.", now()],
        ]
        reorg_id = self.find_control_spreadsheet("ARTSTUDIO_Reorganization_Plan")
        self.replace_sheet(reorg_id, "Native GitHub Validation", VALIDATION_HEADERS, rows)
        self.append_tool_run(
            task="GitHub-native validate readiness",
            output="Native validation report refreshed",
            status="completed",
            review_required="yes" if missing else "no",
            notes="Validation executed from GitHub-native runtime.",
        )
        return {"missingFolders": missing, "controlFilesFound": len(found_control)}

    def should_execute(self, item: Dict[str, str]) -> bool:
        status = normalize(item.get("Execution status"))
        if status == "completed":
            return False
        decision = normalize(item.get("Human decision"))
        if decision in BLOCKING_DECISIONS:
            return False
        action = normalize(item.get("Safe action") or item.get("Recommended action"))
        risk = normalize(item.get("Risk"))
        if risk == "high" and decision != "accepted":
            return False
        if decision == "accepted":
            return action in AUTO_SAFE_ACTIONS
        return decision == "auto-safe" and action in AUTO_SAFE_ACTIONS and risk != "high"

    def execute_row(self, item: Dict[str, str]) -> Dict[str, str]:
        try:
            action = normalize(item.get("Safe action") or item.get("Recommended action"))
            if action == "create folder":
                return self.create_folder_from_row(item)
            if action in {"rename file", "rename folder"}:
                return self.rename_from_row(item)
            if action in {"move file", "move folder", "archive setup artifact", "move methodology file"}:
                return self.move_from_row(item)
            if action == "trash duplicate":
                return self.trash_duplicate_from_row(item)
            return {"status": "blocked", "message": f"No handler for action: {action}"}
        except Exception as exc:  # pragma: no cover - defensive runtime logging
            return {"status": "failed", "message": str(exc)}

    def create_folder_from_row(self, item: Dict[str, str]) -> Dict[str, str]:
        target_name = item.get("Target name")
        target_location = item.get("Target location") or "ARTSTUDIO"
        if not target_name:
            return {"status": "blocked", "message": "Target name is required."}
        parent_id = self.resolve_folder_path(target_location)
        folder_id, created = self.get_or_create_folder(parent_id, target_name)
        return {"status": "completed", "message": f"{'Created' if created else 'Already exists'} folder {target_name} ({folder_id})"}

    def rename_from_row(self, item: Dict[str, str]) -> Dict[str, str]:
        object_id = item.get("Object ID")
        target_name = item.get("Target name")
        if not object_id or not target_name:
            return {"status": "blocked", "message": "Object ID and Target name are required."}
        if not self.dry_run:
            self.services.drive.files().update(fileId=object_id, body={"name": target_name}, supportsAllDrives=True).execute()
        return {"status": "completed", "message": f"Renamed to {target_name}"}

    def move_from_row(self, item: Dict[str, str]) -> Dict[str, str]:
        object_id = item.get("Object ID")
        target_location = item.get("Target location")
        if not object_id or not target_location:
            return {"status": "blocked", "message": "Object ID and Target location are required."}
        target_parent = self.resolve_folder_path(target_location)
        metadata = self.services.drive.files().get(fileId=object_id, fields="parents", supportsAllDrives=True).execute()
        previous_parents = ",".join(metadata.get("parents", []))
        if not self.dry_run:
            self.services.drive.files().update(
                fileId=object_id,
                addParents=target_parent,
                removeParents=previous_parents,
                fields="id, parents",
                supportsAllDrives=True,
            ).execute()
        return {"status": "completed", "message": f"Moved to {target_location}"}

    def trash_duplicate_from_row(self, item: Dict[str, str]) -> Dict[str, str]:
        object_id = item.get("Object ID")
        if not object_id:
            return {"status": "blocked", "message": "Object ID is required."}
        if not self.config["automationPolicy"].get("trashObviousDuplicatesAllowed", False):
            return {"status": "blocked", "message": "Trash duplicate policy is disabled."}
        if self.config["automationPolicy"].get("permanentDeleteAllowed", False):
            return {"status": "blocked", "message": "Permanent delete must remain disabled."}
        compare = normalize(item.get("Compare result"))
        unique_risk = normalize(item.get("Unique content risk"))
        decision = normalize(item.get("Human decision"))
        if compare != "no unique content detected" and unique_risk != "none detected" and decision != "accepted":
            return {"status": "blocked", "message": "Duplicate is not obvious; human review required."}
        if normalize(item.get("Object type")) == "folder" and not self.is_folder_empty(object_id):
            return {"status": "blocked", "message": "Folder is not empty; human review required."}
        if self.dry_run:
            return {"status": "completed", "message": "Dry run: duplicate would be moved to Drive trash."}
        try:
            self.services.drive.files().update(fileId=object_id, body={"trashed": True}, supportsAllDrives=True).execute()
            return {"status": "completed", "message": "Moved duplicate to Drive trash."}
        except HttpError as exc:
            return self.quarantine_pending_trash(
                object_id=object_id,
                reason=f"Drive trash failed for obvious duplicate: {self.http_error_message(exc)}",
            )

    def get_or_create_folder(self, parent_id: str, name: str) -> Tuple[str, bool]:
        existing = self.find_file_in_folder(parent_id, name, mime_type=FOLDER_MIME)
        if existing:
            return existing["id"], False
        if self.dry_run:
            return f"dry-run:{parent_id}:{name}", True
        body = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        created = self.services.drive.files().create(body=body, fields="id", supportsAllDrives=True).execute()
        return created["id"], True

    def resolve_folder_path(self, path: str) -> str:
        path = (path or "ARTSTUDIO").strip().strip("/")
        if path in {"", "ARTSTUDIO"}:
            return self.artstudio_folder_id
        current = self.artstudio_folder_id
        parts = [part for part in path.replace("ARTSTUDIO/", "").split("/") if part]
        for part in parts:
            if part == "00_CONTROL_CENTER":
                current = self.control_center_folder_id
            else:
                current, _ = self.get_or_create_folder(current, part)
        return current

    def pending_trash_folder_id(self) -> str:
        policy = self.config.get("automationPolicy", {})
        path = policy.get(
            "pendingTrashPath",
            f"ARTSTUDIO/00_CONTROL_CENTER/99_Setup_Archive/{PENDING_TRASH_FOLDER_NAME}",
        )
        return self.resolve_folder_path(path)

    def quarantine_pending_trash(self, object_id: str, reason: str) -> Dict[str, str]:
        try:
            metadata = self.services.drive.files().get(
                fileId=object_id,
                fields="id,name,parents",
                supportsAllDrives=True,
            ).execute()
            previous_parents = ",".join(metadata.get("parents", []))
            pending_parent = self.pending_trash_folder_id()
            self.services.drive.files().update(
                fileId=object_id,
                addParents=pending_parent,
                removeParents=previous_parents,
                fields="id,parents",
                supportsAllDrives=True,
            ).execute()
            return {
                "status": "quarantined_pending_trash",
                "message": (
                    f"Trash failed; moved {metadata.get('name', object_id)} ({object_id}) "
                    f"to pending trash folder {pending_parent}. Reason: {reason}"
                ),
            }
        except HttpError as exc:
            return {
                "status": "manual_owner_action_required",
                "message": (
                    f"Trash failed and pending-trash quarantine failed for {object_id}. "
                    f"Trash reason: {reason}. Quarantine reason: {self.http_error_message(exc)}"
                ),
            }

    @staticmethod
    def http_error_message(exc: HttpError) -> str:
        try:
            data = json.loads(exc.content.decode("utf-8"))
            return data.get("error", {}).get("message") or str(exc)
        except Exception:
            return str(exc)

    def list_children(self, parent_id: str, mime_type: Optional[str] = None) -> List[Dict[str, Any]]:
        parent_id = require_drive_id("Parent folder ID", parent_id)
        query = [f"'{parent_id}' in parents", "trashed = false"]
        if mime_type:
            query.append(f"mimeType = '{mime_type}'")
        response = self.services.drive.files().list(
            q=" and ".join(query),
            fields="files(id,name,mimeType,parents,webViewLink,modifiedTime,size)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return response.get("files", [])

    def find_file_in_folder(self, parent_id: str, name: str, mime_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        parent_id = require_drive_id("Parent folder ID", parent_id)
        safe_name = name.replace("'", "\\'")
        query = [f"'{parent_id}' in parents", "trashed = false", f"name = '{safe_name}'"]
        if mime_type:
            query.append(f"mimeType = '{mime_type}'")
        response = self.services.drive.files().list(
            q=" and ".join(query),
            fields="files(id,name,mimeType,webViewLink)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = response.get("files", [])
        return files[0] if files else None

    def is_folder_empty(self, folder_id: str) -> bool:
        return not self.list_children(folder_id)

    def find_control_spreadsheet(self, name: str) -> str:
        if name not in self._control_files:
            file_obj = self.find_file_in_folder(self.control_center_folder_id, name, mime_type=SHEETS_MIME)
            if not file_obj:
                raise RuntimeError(f"Control spreadsheet not found: {name}")
            self._control_files[name] = file_obj["id"]
        return self._control_files[name]

    def get_sheet_values(self, spreadsheet_id: str, sheet_name: str) -> List[List[str]]:
        response = self.services.sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'",
        ).execute()
        return response.get("values", [])

    def ensure_headers(self, spreadsheet_id: str, sheet_name: str, current_headers: List[str], required_headers: List[str]) -> None:
        missing = [header for header in required_headers if header not in current_headers]
        if not missing:
            return
        start_col = len(current_headers) + 1
        end_col = start_col + len(missing) - 1
        self.services.sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!{column_name(start_col)}1:{column_name(end_col)}1",
            valueInputOption="USER_ENTERED",
            body={"values": [missing]},
        ).execute()

    def replace_sheet(self, spreadsheet_id: str, sheet_name: str, headers: List[str], rows: List[List[str]]) -> None:
        metadata = self.services.sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_exists = any(s["properties"]["title"] == sheet_name for s in metadata.get("sheets", []))
        requests = [] if sheet_exists else [{"addSheet": {"properties": {"title": sheet_name}}}]
        if requests and not self.dry_run:
            self.services.sheets.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()
        if not self.dry_run:
            self.services.sheets.spreadsheets().values().clear(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'").execute()
            self.services.sheets.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [headers] + rows},
            ).execute()

    def update_execution_cells(self, spreadsheet_id: str, sheet_name: str, headers: List[str], row_number: int, result: Dict[str, str]) -> None:
        updates = {
            "Execution status": result["status"],
            "Execution log": result["message"],
            "Executed by": "GitHub Actions service account",
            "Last checked": now(),
        }
        data = []
        for header, value in updates.items():
            if header in headers:
                col = column_name(headers.index(header) + 1)
                data.append({"range": f"'{sheet_name}'!{col}{row_number}", "values": [[value]]})
        if data and not self.dry_run:
            self.services.sheets.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": data},
            ).execute()

    def append_tool_run(self, task: str, output: str, status: str, review_required: str, notes: str = "") -> None:
        try:
            spreadsheet_id = self.find_control_spreadsheet("ARTSTUDIO_Tool_Run_Log")
            values = self.get_sheet_values(spreadsheet_id, "ARTSTUDIO_Tool_Run_Log")
            if not values:
                values = [TOOL_RUN_HEADERS]
            self.ensure_headers(spreadsheet_id, "ARTSTUDIO_Tool_Run_Log", values[0], TOOL_RUN_HEADERS)
            row = [
                "GHA-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
                now(),
                "GitHub Actions service account",
                task,
                "GitHub repo; Google Drive; control-center config",
                output,
                "ARTSTUDIO_Reorganization_Plan; ARTSTUDIO_Tool_Run_Log",
                status,
                review_required,
                "",
                notes,
            ]
            if not self.dry_run:
                self.services.sheets.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range="'ARTSTUDIO_Tool_Run_Log'!A1",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row]},
                ).execute()
        except Exception as exc:
            print(f"Tool Run Log update skipped: {exc}", file=sys.stderr)

    @staticmethod
    def row_to_item(headers: List[str], row: List[str]) -> Dict[str, str]:
        return {header: row[idx] if idx < len(row) else "" for idx, header in enumerate(headers)}

    @staticmethod
    def execution_run_status(results: List[Dict[str, str]]) -> str:
        statuses = {result.get("status") for result in results}
        if "failed" in statuses:
            return "completed with errors"
        if "manual_owner_action_required" in statuses or "blocked" in statuses:
            return "completed with manual actions"
        return "completed"

    @staticmethod
    def execution_needs_review(results: List[Dict[str, str]]) -> bool:
        return any(result.get("status") in {"blocked", "manual_owner_action_required"} for result in results)


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def build_services() -> Services:
    credentials = load_service_account_credentials()
    return Services(
        drive=build("drive", "v3", credentials=credentials, cache_discovery=False),
        sheets=build("sheets", "v4", credentials=credentials, cache_discovery=False),
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="ARTSTUDIO GitHub-native Drive operations")
    parser.add_argument("command", choices=["prepare-structure", "execute-safe-actions", "validate-readiness"])
    parser.add_argument("--config", default="config/control-center.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    ops = KnowledgeOps(config=config, services=build_services(), dry_run=args.dry_run)
    if args.command == "prepare-structure":
        result = ops.prepare_structure()
    elif args.command == "execute-safe-actions":
        result = ops.execute_safe_actions()
    elif args.command == "validate-readiness":
        result = ops.validate_readiness()
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
