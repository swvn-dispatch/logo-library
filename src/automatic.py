"""Validation for group-scoped automatic matching configuration."""

from collections import Counter
from pathlib import PurePosixPath


def compile_groups(rows, group_ids, catalog_ids):
    """Return valid enabled settings keyed by stable group ID and row errors.

    Duplicate groups are all rejected, rather than picking a potentially unsafe
    replacement policy based on row order. Matching is deliberately separate.
    """
    if not isinstance(rows, list):
        return {}, ["Group settings must be a list"]
    counts = Counter(str(row["group"]) for row in rows if isinstance(row, dict)
                     and row.get("group") not in (None, ""))
    groups = {str(group) for group in group_ids}
    compiled, errors = {}, []
    for index, row in enumerate(rows, 1):
        try:
            if not isinstance(row, dict) or row.get("group") in (None, ""):
                raise ValueError("Select a group")
            group = str(row["group"])
            if counts[group] > 1:
                raise ValueError("Group is configured more than once")
            if group not in groups:
                raise ValueError("Group no longer exists")
            strategy = row.get("strategy") or "disabled"
            if strategy == "disabled":
                continue
            if strategy not in {"exact", "callsign", "fuzzy"}:
                raise ValueError("Unknown strategy")
            if row.get("catalog") not in catalog_ids:
                raise ValueError("Select an available catalog")
            scope = row.get("scope") or ""
            if not isinstance(scope, str) or "\\" in scope or "\x00" in scope:
                raise ValueError("Invalid path scope")
            path = PurePosixPath(scope)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Path scope must be a catalog-relative directory")
            replace = row.get("replace")
            if replace not in (None, True, False) or not isinstance(replace, (bool, type(None))):
                raise ValueError("Replace existing logos must be a boolean")
            prefix = row.get("prefix") or ""
            if not isinstance(prefix, str):
                raise ValueError("Name prefix must be text")
            threshold = row.get("threshold")
            if strategy == "fuzzy" and (isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 100):
                raise ValueError("Fuzzy threshold must be between 0 and 100")
            compiled[group] = {"strategy": strategy, "catalog": row["catalog"],
                               "scope": "" if not scope else str(path), "replace": bool(replace),
                               "prefix": prefix, "threshold": threshold}
        except ValueError as exc:
            errors.append(f"Row {index}: {exc}")
    return compiled, errors
