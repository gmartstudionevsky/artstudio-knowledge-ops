from __future__ import annotations

import json
import os
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

READ_ONLY_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def load_read_only_credentials() -> service_account.Credentials:
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    json_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    delegated_user = os.environ.get("GOOGLE_DELEGATED_USER")

    if raw_json:
        info = json.loads(raw_json)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=READ_ONLY_SCOPES)
    elif json_path:
        credentials = service_account.Credentials.from_service_account_file(json_path, scopes=READ_ONLY_SCOPES)
    else:
        raise RuntimeError("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS.")

    if delegated_user:
        credentials = credentials.with_subject(delegated_user)
    return credentials


def build_read_only_drive_service() -> Any:
    return build("drive", "v3", credentials=load_read_only_credentials(), cache_discovery=False)
