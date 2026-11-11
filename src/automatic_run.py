"""Orchestrate group matching with a guarded, injected assignment function."""

from collections import Counter

from .automatic import compile_groups
from .callsign_matching import build_callsign_index, match_callsign
from .fuzzy_matching import match_fuzzy
from .name_matching import build_name_index, match_name


def run_automatic(data_dir, settings, channels, group_ids, catalogs, assign):
    """Match a snapshot; assign must recheck eligibility under a write lock.

    The injected assign function receives (channel_id, group_id, channel_name,
    group_config, logo_identity, image). It returns None on success or a skip
    reason if the channel or saved settings changed since the snapshot.
    """
    manual = settings.get("mappings", [])
    if not isinstance(manual, list):
        raise ValueError("Manual mappings must be a list")
    manual_ids = {str(row["channel"]) for row in manual if isinstance(row, dict)
                  and row.get("channel") not in (None, "")}
    catalog_by_id = {catalog.id: catalog for catalog in catalogs}
    group_ids = {str(group) for group in group_ids}
    groups, errors = compile_groups(settings.get("automatic_groups", []), group_ids, catalog_by_id, settings)
    result = {"applied": 0, "skipped": 0, "failed": 0, "channels": [], "configuration_errors": errors}
    channels = list(channels)
    counts = Counter(str(channel["id"]) for channel in channels)
    indices = {}
    for channel in channels:
        channel_id = str(channel["id"])
        group_id = str(channel["group_id"]) if channel.get("group_id") is not None else None
        detail = {"channel": channel_id, "name": channel.get("name", ""), "group": group_id}
        try:
            config = groups.get(group_id)
            if counts[channel_id] > 1:
                reason = "duplicate_channel"
            elif channel_id in manual_ids:
                reason = "manual_mapping"
            elif group_id is None or group_id not in group_ids:
                reason = "missing_group"
            elif config is None:
                reason = "group_not_enabled"
            elif channel.get("logo_id") is not None and not config["replace"]:
                reason = "existing_logo"
            else:
                catalog = catalog_by_id[config["catalog"]]
                key = (catalog.id, config["scope"], config["strategy"] == "callsign")
                if key not in indices:
                    paths = catalog.options(data_dir)
                    indices[key] = (build_callsign_index(paths, catalog.id, config["scope"]) if key[2]
                                    else build_name_index(paths, catalog.id, config["scope"]))
                index = indices[key]
                if config["strategy"] == "callsign":
                    match = match_callsign(channel["name"], index)
                elif config["strategy"] == "fuzzy":
                    match = match_fuzzy(channel["name"], index, config["threshold"], config["prefix"])
                else:
                    match = match_name(channel["name"], index, config["prefix"])
                if match.get("score") is not None:
                    detail["score"] = match["score"]
                reason = match["reason"]
                if reason is None:
                    identity = f"{catalog.id}:{match['path']}"
                    with catalog.resolve(data_dir, match["path"]) as image:
                        reason = assign(channel_id, group_id, channel["name"], config, identity, image)
                    if reason is None:
                        detail["logo"] = identity
            if reason is None:
                result["applied"] += 1
                detail["status"] = "applied"
            else:
                result["skipped"] += 1
                detail.update(status="skipped", reason=reason)
        except Exception as exc:
            result["failed"] += 1
            detail.update(status="failed", reason=str(exc))
        result["channels"].append(detail)
    return result
