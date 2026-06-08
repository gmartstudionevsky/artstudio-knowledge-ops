from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from knowledge_ops.ai_analysis.config import load_yaml


@dataclass(frozen=True)
class PriceEntry:
    service: str
    feature: str
    unit: str
    free_tier_units: float
    unit_size: float
    price_per_unit_usd: float
    currency: str = "USD"
    notes: str = ""
    effective_date: str = ""
    source_url: str = ""
    manually_reviewed: bool = False


class PricingTable:
    def __init__(self, entries: Dict[Tuple[str, str], PriceEntry]):
        self.entries = entries

    @classmethod
    def from_file(cls, path: str | Path) -> "PricingTable":
        data = load_yaml(path)
        entries: Dict[Tuple[str, str], PriceEntry] = {}
        for service, features in data.items():
            if not isinstance(features, dict):
                continue
            for feature, item in features.items():
                if not isinstance(item, dict):
                    continue
                entry = PriceEntry(
                    service=service,
                    feature=feature,
                    unit=item.get("unit", "unit"),
                    free_tier_units=float(item.get("free_tier_units", 0)),
                    unit_size=float(item.get("unit_size", 1)),
                    price_per_unit_usd=float(item.get("price_per_unit_usd", 0)),
                    currency=item.get("currency", "USD"),
                    notes=item.get("notes", ""),
                    effective_date=item.get("effective_date", ""),
                    source_url=item.get("source_url", ""),
                    manually_reviewed=bool(item.get("manually_reviewed", False)),
                )
                entries[(service, feature)] = entry
        return cls(entries)

    def cost(self, service: str, feature: str, units: float) -> float:
        entry = self.entries.get((service, feature))
        if not entry:
            return 0.0
        billable = max(0.0, units - entry.free_tier_units)
        return (billable / max(entry.unit_size, 1.0)) * entry.price_per_unit_usd
