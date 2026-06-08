from __future__ import annotations

import os


class CloudAnalysisSafetyError(RuntimeError):
    pass


def assert_estimate_mode_safe(mode: str) -> None:
    if mode == "analyze-sample" and os.environ.get("AI_ANALYSIS_ALLOW_CLOUD_CALLS", "false").lower() != "true":
        raise CloudAnalysisSafetyError("Cloud calls are disabled. Set AI_ANALYSIS_ALLOW_CLOUD_CALLS=true for future analyze-sample mode.")


def assert_sensitive_upload_allowed(has_sensitive: bool) -> None:
    if has_sensitive and os.environ.get("AI_ANALYSIS_ALLOW_SENSITIVE_UPLOAD", "false").lower() != "true":
        raise CloudAnalysisSafetyError("Sensitive uploads are disabled by default.")
