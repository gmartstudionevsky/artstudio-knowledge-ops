from __future__ import annotations

FORBIDDEN_DRIVE_METHODS = {
    "files.create",
    "files.update",
    "files.delete",
    "files.copy",
    "files.emptyTrash",
    "permissions.create",
    "permissions.update",
    "permissions.delete",
    "revisions.update",
    "drives.create",
    "drives.update",
    "drives.delete",
}

FORBIDDEN_RECOMMENDATIONS = {"DELETE", "PERMANENT_DELETE", "TRASH_NOW"}


class ReadOnlySafetyError(RuntimeError):
    pass


def assert_read_only_operation(operation: str) -> None:
    if operation in FORBIDDEN_DRIVE_METHODS:
        raise ReadOnlySafetyError(f"Drive inventory is read-only; forbidden operation requested: {operation}")


def assert_safe_recommendation(recommendation: str) -> None:
    if (recommendation or "").strip().upper() in FORBIDDEN_RECOMMENDATIONS:
        raise ReadOnlySafetyError("First-stage inventory must not recommend delete/destructive actions.")


class ReadOnlyResourceProxy:
    """Small guard for Google API resources used by the inventory client."""

    def __init__(self, resource: object, prefix: str = ""):
        self._resource = resource
        self._prefix = prefix

    def __getattr__(self, name: str):
        attr = getattr(self._resource, name)
        operation = f"{self._prefix}.{name}" if self._prefix else name
        if callable(attr):
            def guarded(*args, **kwargs):
                assert_read_only_operation(operation)
                result = attr(*args, **kwargs)
                if name in {"files", "permissions", "revisions", "drives"}:
                    return ReadOnlyResourceProxy(result, name)
                return result

            return guarded
        return attr
