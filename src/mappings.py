"""Validate and apply saved manual channel mappings."""

from collections import Counter

from . import catalogs


def manual_configuration_snapshot(rows, channels=()):
    """Describe manual definitions without exposing internal channel IDs."""
    if not isinstance(rows, list):
        return {"snapshot": "start_of_run", "mappings": "<invalid>"}
    channel_by_id = {str(channel["id"]): channel for channel in channels}

    def scalar(value):
        return value if value is None or isinstance(value, (str, int, float, bool)) else "<invalid>"

    mappings = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            mappings.append({"row": index, "invalid": True})
            continue
        channel = channel_by_id.get(str(row.get("channel")), {})
        mappings.append({"row": index, "channel": channel.get("number"), "name": channel.get("name"),
                         "logo": scalar(row.get("logo")), "ignore": scalar(row.get("ignore"))})
    return {"snapshot": "start_of_run", "mappings": mappings}


def automatic_ignored_channels(settings):
    """Return ignored IDs, retaining old checked rows until the list is saved."""
    if "automatic_ignored_channels" not in settings:
        rows = settings.get("mappings", [])
        if not isinstance(rows, list):
            raise ValueError("Mappings must be a list")
        values = [row.get("channel") for row in rows if isinstance(row, dict)
                  and row.get("ignore") is True and row.get("channel") not in (None, "")]
    else:
        values = settings["automatic_ignored_channels"]
        if not isinstance(values, list):
            raise ValueError("Channels to ignore must be a list")
    result = set()
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).isascii() or not str(value).isdigit() or int(value) <= 0:
            raise ValueError("Channels to ignore must contain valid channel IDs")
        result.add(str(int(value)))
    return result


def manual_disposition(rows):
    """Classify saved rows for one channel without claiming a logo was applied."""
    if not rows:
        return None
    if len(rows) > 1:
        return "manual_mapping_conflict"
    row = rows[0]
    ignore = row.get("ignore")
    if ignore is not None and not isinstance(ignore, bool):
        return "manual_mapping_invalid"
    if ignore is True:
        return "ignored"
    if not isinstance(row.get("logo"), str) or not row["logo"].strip():
        return "manual_mapping_incomplete"
    return "manual_mapping"


def apply_mappings(data_dir, rows, assign):
    """Apply valid rows with an injected Dispatcharr assignment function.

    `assign` receives a channel ID, relative path, and local image path. Each
    failure is isolated so a bad mapping cannot prevent unrelated assignments.
    """
    if not isinstance(rows, list):
        raise ValueError("Mappings must be a list")
    counts = Counter(str(row.get("channel")) for row in rows
                     if isinstance(row, dict) and row.get("channel") not in (None, ""))
    result = {"applied": 0, "ignored": 0, "skipped": 0, "errors": []}
    for index, row in enumerate(rows, 1):
        channel = row.get("channel") if isinstance(row, dict) else None
        try:
            if not isinstance(row, dict) or channel in (None, ""):
                raise ValueError("Select a channel")
            if counts[str(channel)] > 1:
                raise ValueError("Channel is mapped more than once")
            disposition = manual_disposition([row])
            if disposition == "manual_mapping_invalid":
                raise ValueError("Ignore must be a boolean")
            if disposition == "ignored":
                result["ignored"] += 1
                continue
            catalog, path = catalogs.parse_logo(row.get("logo"))
            with catalog.resolve(data_dir, path) as image:
                assign(str(channel), f"{catalog.id}:{path}", image)
            result["applied"] += 1
        except Exception as exc:
            result["skipped"] += 1
            result["errors"].append({"row": index, "channel": str(channel or ""), "message": str(exc)})
    return result
