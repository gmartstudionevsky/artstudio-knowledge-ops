from __future__ import annotations

from typing import Dict, List

from knowledge_ops.ai_analysis.config import load_yaml


def load_scenario_features(path: str) -> Dict[str, Dict[str, List[str]]]:
    data = load_yaml(path)
    return data.get("scenarios", {})
