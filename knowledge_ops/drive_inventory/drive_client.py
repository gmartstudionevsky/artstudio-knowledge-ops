from __future__ import annotations

import hashlib
import io
from typing import Any, Dict, Iterator, Optional

from googleapiclient.http import MediaIoBaseDownload

from knowledge_ops.drive_inventory.config import InventoryConfig
from knowledge_ops.drive_inventory.models import DOCS_MIME, SHEETS_MIME, SLIDES_MIME
from knowledge_ops.drive_inventory.safety import ReadOnlyResourceProxy

FILE_FIELDS = (
    "nextPageToken, files("
    "id,name,mimeType,size,md5Checksum,webViewLink,createdTime,modifiedTime,viewedByMeTime,"
    "owners(displayName,emailAddress),lastModifyingUser(displayName,emailAddress),parents,driveId,"
    "trashed,starred,shared,capabilities(canEdit,canShare,canDelete)"
    ")"
)


class DriveInventoryClient:
    def __init__(self, service: Any, config: InventoryConfig):
        self.service = ReadOnlyResourceProxy(service) if config.safe_mode else service
        self.config = config

    def iter_all_accessible(self, max_files: int = 0) -> Iterator[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {
            "q": "trashed = false",
            "fields": FILE_FIELDS,
            "pageSize": self.config.page_size,
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "corpora": "allDrives",
        }
        yield from self._iter_files(kwargs, max_files=max_files)

    def iter_folder_tree(self, root_folder_id: str, max_files: int = 0) -> Iterator[Dict[str, Any]]:
        seen = 0
        queue = [root_folder_id]
        yielded_ids = set()
        while queue:
            folder_id = queue.pop(0)
            kwargs = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": FILE_FIELDS,
                "pageSize": self.config.page_size,
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }
            for file_obj in self._iter_files(kwargs):
                if file_obj.get("id") in yielded_ids:
                    continue
                yielded_ids.add(file_obj.get("id"))
                seen += 1
                yield file_obj
                if file_obj.get("mimeType") == "application/vnd.google-apps.folder":
                    queue.append(file_obj["id"])
                if max_files and seen >= max_files:
                    return

    def get_file(self, file_id: str) -> Dict[str, Any]:
        return self.service.files().get(fileId=file_id, fields=FILE_FIELDS.removeprefix("nextPageToken, files(").removesuffix(")"), supportsAllDrives=True).execute()

    def calculate_content_hash(self, file_obj: Dict[str, Any]) -> str:
        if file_obj.get("mimeType", "").startswith("application/vnd.google-apps."):
            return ""
        size = int(file_obj.get("size") or 0)
        if size > self.config.max_download_bytes:
            return ""
        request = self.service.files().get_media(fileId=file_obj["id"])
        return self._download_hash(request)

    def calculate_export_hash(self, file_obj: Dict[str, Any]) -> str:
        mime_type = file_obj.get("mimeType", "")
        if mime_type == SHEETS_MIME:
            return ""
        export_mime = export_mime_type(mime_type)
        if not export_mime:
            return ""
        request = self.service.files().export_media(fileId=file_obj["id"], mimeType=export_mime)
        return self._download_hash(request)

    def _download_hash(self, request: Any) -> str:
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
            if fh.tell() > self.config.max_download_bytes:
                return ""
        return hashlib.sha256(fh.getvalue()).hexdigest()

    def _iter_files(self, kwargs: Dict[str, Any], max_files: int = 0) -> Iterator[Dict[str, Any]]:
        count = 0
        page_token: Optional[str] = None
        while True:
            if page_token:
                kwargs["pageToken"] = page_token
            response = self.service.files().list(**kwargs).execute()
            for file_obj in response.get("files", []):
                count += 1
                yield file_obj
                if max_files and count >= max_files:
                    return
            page_token = response.get("nextPageToken")
            if not page_token:
                return


def export_mime_type(mime_type: str) -> str:
    if mime_type == DOCS_MIME:
        return "text/plain"
    if mime_type == SLIDES_MIME:
        return "text/plain"
    return ""
