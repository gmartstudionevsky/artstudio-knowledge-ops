from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError

from knowledge_ops.native_drive_ops import (
    AUTO_SAFE_ACTIONS,
    FOLDER_MIME,
    KnowledgeOps,
    build_services,
    load_config,
    normalize,
    now,
)
from knowledge_ops.preparation_ops import PreparationOps

AUTO_SAFE_ACTIONS.add("quarantine pending trash")

PENDING_TRASH_HEADERS = [
    "Queue ID",
    "Date / time",
    "Object ID",
    "Object name",
    "Object type",
    "Previous parents",
    "Pending trash folder ID",
    "Source action",
    "Reason",
    "Execution status",
    "Execution log",
    "Object URL",
    "Last checked",
]


class StrictKnowledgeOps(KnowledgeOps):
    """Strict runtime for preparation-stage Drive operations.

    The key policy difference from the legacy native module is that delete-like
    automation is represented as a logged quarantine move. Permanent delete is
    still unavailable, and Drive trash is only used when explicitly configured.
    """

    def prepare_structure(self) -> Dict[str, Any]:
        result = super().prepare_structure()
        pending_result = self.ensure_pending_trash_folder()
        result["pendingTrash"] = pending_result
        return result

    def execute_row(self, item: Dict[str, str]) -> Dict[str, str]:
        action = normalize(item.get("Safe action") or item.get("Recommended action"))
        if action == "quarantine pending trash":
            object_id = item.get("Object ID")
            if not object_id:
                return {"status": "blocked", "message": "Object ID is required."}
            return self.quarantine_pending_trash(
                object_id=object_id,
                reason=item.get("Machine recommendation") or "Approved pending-trash quarantine row.",
                source_action="quarantine pending trash",
            )
        return super().execute_row(item)

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

        reason = (
            "Obvious duplicate approved by Reorganization Plan. "
            f"Compare result: {item.get('Compare result', '')}; "
            f"unique content risk: {item.get('Unique content risk', '')}."
        )
        policy = self.config.get("automationPolicy", {})
        if self.dry_run:
            return {
                "status": "completed",
                "message": "Dry run: duplicate would be moved to pending-trash quarantine.",
            }
        if policy.get("quarantinePendingTrashPrimary", True):
            return self.quarantine_pending_trash(
                object_id=object_id,
                reason=reason,
                source_action="trash duplicate",
            )

        try:
            self.services.drive.files().update(
                fileId=object_id,
                body={"trashed": True},
                supportsAllDrives=True,
            ).execute()
            return {"status": "completed", "message": "Moved duplicate to Drive trash."}
        except HttpError as exc:
            return self.quarantine_pending_trash(
                object_id=object_id,
                reason=f"Drive trash failed for obvious duplicate: {self.http_error_message(exc)}",
                source_action="trash duplicate fallback",
            )

    def ensure_pending_trash_folder(self) -> Dict[str, str]:
        policy = self.config.get("automationPolicy", {})
        if not policy.get("pendingTrashFallbackAllowed", True):
            return {"status": "disabled", "message": "Pending-trash quarantine policy is disabled."}
        path = policy.get("pendingTrashPath") or "ARTSTUDIO/00_CONTROL_CENTER/99_Setup_Archive/00_PENDING_TRASH"
        folder_id = self.resolve_folder_path(path)
        return {"status": "ready", "message": f"Pending-trash folder ready: {path} ({folder_id})", "folderId": folder_id}

    def quarantine_pending_trash(self, object_id: str, reason: str, source_action: str = "pending trash fallback") -> Dict[str, str]:
        policy = self.config.get("automationPolicy", {})
        if not policy.get("pendingTrashFallbackAllowed", True):
            return {"status": "manual_owner_action_required", "message": "Pending-trash quarantine policy is disabled."}

        try:
            metadata = self.services.drive.files().get(
                fileId=object_id,
                fields="id,name,mimeType,parents,webViewLink",
                supportsAllDrives=True,
            ).execute()
            pending_parent = self.pending_trash_folder_id()
            if object_id == pending_parent:
                return {"status": "blocked", "message": "Refusing to quarantine the pending-trash folder itself."}

            parents = metadata.get("parents", [])
            previous_parents = ",".join(parents)
            message_prefix = f"Moved {metadata.get('name', object_id)} ({object_id}) to pending-trash folder {pending_parent}."
            if pending_parent in parents and len(parents) == 1:
                status = "quarantined_pending_trash"
                message = f"Already quarantined in pending-trash folder {pending_parent}. Reason: {reason}"
            elif self.dry_run:
                status = "completed"
                message = f"Dry run: {message_prefix} Reason: {reason}"
            else:
                remove_parents = [parent for parent in parents if parent != pending_parent]
                update_kwargs: Dict[str, Any] = {
                    "fileId": object_id,
                    "addParents": pending_parent,
                    "fields": "id,parents",
                    "supportsAllDrives": True,
                }
                if remove_parents:
                    update_kwargs["removeParents"] = ",".join(remove_parents)
                self.services.drive.files().update(**update_kwargs).execute()
                status = "quarantined_pending_trash"
                message = f"{message_prefix} Reason: {reason}"

            if not self.dry_run:
                self.append_pending_trash_queue(
                    metadata=metadata,
                    previous_parents=previous_parents,
                    pending_parent=pending_parent,
                    source_action=source_action,
                    reason=reason,
                    status=status,
                    message=message,
                )
                self.append_tool_run(
                    task="Quarantine pending-trash object",
                    output=message,
                    status=status,
                    review_required="no",
                    notes=f"Source action: {source_action}. Permanent delete is disabled.",
                )
            return {"status": status, "message": message}
        except HttpError as exc:
            return {
                "status": "manual_owner_action_required",
                "message": (
                    f"Pending-trash quarantine failed for {object_id}. "
                    f"Reason: {reason}. Drive error: {self.http_error_message(exc)}"
                ),
            }

    def append_pending_trash_queue(
        self,
        metadata: Dict[str, Any],
        previous_parents: str,
        pending_parent: str,
        source_action: str,
        reason: str,
        status: str,
        message: str,
    ) -> None:
        spreadsheet_id = self.find_control_spreadsheet("ARTSTUDIO_Reorganization_Plan")
        sheet_name = self.config.get("automationPolicy", {}).get("pendingTrashQueueSheet", "Pending Trash Queue")
        self.ensure_sheet_exists(spreadsheet_id, sheet_name)
        values = self.get_sheet_values(spreadsheet_id, sheet_name)
        if not values:
            self.services.sheets.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [PENDING_TRASH_HEADERS]},
            ).execute()
            headers = PENDING_TRASH_HEADERS
        else:
            headers = values[0]
            self.ensure_headers(spreadsheet_id, sheet_name, headers, PENDING_TRASH_HEADERS)
            headers = self.get_sheet_values(spreadsheet_id, sheet_name)[0]

        row_by_header = {
            "Queue ID": "GHA-PT-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
            "Date / time": now(),
            "Object ID": metadata.get("id", ""),
            "Object name": metadata.get("name", ""),
            "Object type": metadata.get("mimeType", ""),
            "Previous parents": previous_parents,
            "Pending trash folder ID": pending_parent,
            "Source action": source_action,
            "Reason": reason,
            "Execution status": status,
            "Execution log": message,
            "Object URL": metadata.get("webViewLink", ""),
            "Last checked": now(),
        }
        row = [row_by_header.get(header, "") for header in headers]
        self.services.sheets.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    def ensure_sheet_exists(self, spreadsheet_id: str, sheet_name: str) -> None:
        metadata = self.services.sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        exists = any(sheet["properties"]["title"] == sheet_name for sheet in metadata.get("sheets", []))
        if not exists:
            self.services.sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
            ).execute()


class StrictPreparationOps(PreparationOps, StrictKnowledgeOps):
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
        if self.dry_run:
            return {
                "status": "completed",
                "message": (
                    f"Dry run: would merge duplicate folder {duplicate['name']} ({duplicate['id']}) "
                    f"into {canonical['id']}, move {moved} children, then quarantine pending trash."
                ),
            }
        return self.quarantine_pending_trash(
            object_id=duplicate["id"],
            reason=f"Duplicate root folder merged into canonical folder {canonical['id']}; moved children: {moved}.",
            source_action="merge duplicate root folder",
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="ARTSTUDIO strict GitHub-native Drive operations")
    parser.add_argument(
        "command",
        choices=[
            "prepare-structure",
            "execute-safe-actions",
            "validate-readiness",
            "plan-reorganization",
            "prepare-and-plan",
            "complete-prep",
        ],
    )
    parser.add_argument("--config", default="config/control-center.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    services = build_services()
    if args.command in {"plan-reorganization", "prepare-and-plan", "complete-prep"}:
        ops: KnowledgeOps = StrictPreparationOps(config=config, services=services, dry_run=args.dry_run)
    else:
        ops = StrictKnowledgeOps(config=config, services=services, dry_run=args.dry_run)

    if args.command == "prepare-structure":
        result = ops.prepare_structure()
    elif args.command == "execute-safe-actions":
        result = ops.execute_safe_actions()
    elif args.command == "validate-readiness":
        result = ops.validate_readiness()
    elif args.command == "plan-reorganization":
        result = ops.plan_reorganization(write_main=True)  # type: ignore[attr-defined]
    elif args.command == "prepare-and-plan":
        result = ops.prepare_and_plan()  # type: ignore[attr-defined]
    elif args.command == "complete-prep":
        result = ops.complete_preparation()  # type: ignore[attr-defined]
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
