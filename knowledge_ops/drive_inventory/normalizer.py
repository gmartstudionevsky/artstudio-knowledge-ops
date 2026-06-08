from __future__ import annotations

import re
import unicodedata
from pathlib import PurePath
from typing import Dict, List, Tuple

VERSION_MARKERS = [
    "копия",
    "copy",
    "final",
    "финал",
    "новый",
    "старая версия",
    "актуально",
    "актуальный",
    "old",
    "draft",
    "черновик",
    "версия",
    "дубль",
]


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u00a0", " ")).strip()


def normalize_name(name: str) -> str:
    value = unicodedata.normalize("NFKC", normalize_spaces(name)).lower()
    value = value.replace("ё", "е")
    value = re.sub(r"[_\-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def split_extension(name: str, mime_type: str = "") -> Tuple[str, str]:
    if mime_type.startswith("application/vnd.google-apps."):
        return name, ""
    suffix = PurePath(name).suffix.lower().lstrip(".")
    if not suffix or len(suffix) > 12:
        return name, ""
    return name[: -(len(suffix) + 1)], suffix


def strip_version_markers(name: str) -> str:
    value = normalize_name(name)
    for marker in VERSION_MARKERS:
        value = re.sub(rf"\b{re.escape(marker)}\b", " ", value)
    value = re.sub(r"\bv\s*\d+\b", " ", value)
    value = re.sub(r"\(\s*\d+\s*\)", " ", value)
    value = re.sub(r"\b\d{4}[-_. ]?\d{2}[-_. ]?\d{2}\b", " ", value)
    return normalize_spaces(value)


def extract_name_features(name: str, path: str = "") -> Dict[str, List[str]]:
    text = normalize_name(f"{path} {name}")
    return {
        "years": sorted(set(re.findall(r"\b(20\d{2}|19\d{2})\b", text))),
        "dates": sorted(set(re.findall(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}\b", text))),
        "apartments": sorted(set(re.findall(r"(?:ап|апарт|кв|unit|room|номер)\s*[\-№#]?\s*([a-zа-я0-9\-]+)", text))),
        "contracts": sorted(set(re.findall(r"(?:договор|contract|дог)\s*[\-№#]?\s*([a-zа-я0-9\-/.]+)", text))),
        "acts": sorted(set(re.findall(r"(?:акт|act)\s*[\-№#]?\s*([a-zа-я0-9\-/.]+)", text))),
        "invoices": sorted(set(re.findall(r"(?:счет|счёт|invoice)\s*[\-№#]?\s*([a-zа-я0-9\-/.]+)", text))),
        "registries": sorted(set(re.findall(r"(?:реестр|registry)\s*[\-№#]?\s*([a-zа-я0-9\-/.]+)", text))),
    }
