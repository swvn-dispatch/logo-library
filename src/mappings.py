"""Validate and apply saved manual channel mappings."""

from collections import Counter

from . import catalogs


def apply_mappings(data_dir, rows, assign):
    """Apply valid rows with an injected Dispatcharr assignment function.

    `assign` receives a channel ID, relative path, and local image path. Each
    failure is isolated so a bad mapping cannot prevent unrelated assignments.
    """
    if not isinstance(rows, list):
        raise ValueError("Mappings must be a list")
    counts = Counter(str(row.get("channel")) for row in rows
                     if isinstance(row, dict) and row.get("channel") not in (None, ""))
    result = {"applied": 0, "skipped": 0, "errors": []}
    for index, row in enumerate(rows, 1):
        channel = row.get("channel") if isinstance(row, dict) else None
        try:
            if not isinstance(row, dict) or channel in (None, ""):
                raise ValueError("Select a channel")
            if counts[str(channel)] > 1:
                raise ValueError("Channel is mapped more than once")
            catalog, path = catalogs.parse_logo(row.get("logo"))
            with catalog.resolve(data_dir, path) as image:
                assign(str(channel), f"{catalog.id}:{path}", image)
            result["applied"] += 1
        except Exception as exc:
            result["skipped"] += 1
            result["errors"].append({"row": index, "channel": str(channel or ""), "message": str(exc)})
    return result
