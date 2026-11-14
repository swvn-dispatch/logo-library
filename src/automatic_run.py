"""Orchestrate group matching with a guarded, injected assignment function."""

from collections import Counter, defaultdict

from .automatic import compile_groups
from .callsign_matching import build_callsign_index, build_station_name_index
from .catalog_scope import scoped_paths
from .channel_patterns import channel_matches, compile_patterns
from .filters import catalog_filter_rules, matches
from .matching_engine import build_network_index, match_channel
from .mappings import automatic_ignored_channels, manual_disposition
from .name_matching import build_name_index


def run_automatic(data_dir, settings, channels, group_ids, catalogs, assign):
    """Match a snapshot; assign must recheck eligibility under a write lock.

    The injected assign function receives (channel_id, group_id, channel_name,
    guide_id, group_config, logo_identity, image). It returns None on success or a skip
    reason if the channel or saved settings changed since the snapshot.
    """
    manual = settings.get("mappings", [])
    if not isinstance(manual, list):
        raise ValueError("Manual mappings must be a list")
    manual_rows = defaultdict(list)
    for row in manual:
        # Old checked rows remain non-assigning in Manual Match until removed,
        # but the new list is authoritative once it has been saved.
        if isinstance(row, dict) and row.get("ignore") is not True and row.get("channel") not in (None, ""):
            manual_rows[str(row["channel"])].append(row)
    catalogs = tuple(catalogs)
    catalog_by_id = {catalog.id: catalog for catalog in catalogs}
    group_ids = {str(group) for group in group_ids}
    groups, errors = compile_groups(settings.get("automatic_groups", []), group_ids, catalog_by_id, settings)
    enabled_groups = dict(groups)
    try:
        ignored_channels = automatic_ignored_channels(settings)
    except ValueError as exc:
        ignored_channels = set()
        errors.append(str(exc))
        groups.clear()
    filter_rules, filter_errors = catalog_filter_rules(settings.get("catalog_filters", []), catalogs)
    hints, hint_errors = compile_patterns(settings.get("automatic_channel_hints", []), hints=True)
    ignore_patterns, ignore_errors = compile_patterns(settings.get("automatic_ignore_patterns", []))
    if hint_errors or ignore_errors:
        errors.extend(f"Channel hint: {error}" for error in hint_errors)
        errors.extend(f"Ignore pattern: {error}" for error in ignore_errors)
        groups.clear()
    if filter_errors:
        errors.extend(f"Catalog filter: {error}" for error in filter_errors)
        groups.clear()
    catalog_paths = {}
    for group_id, config in list(groups.items()):
        try:
            catalog = catalog_by_id[config["catalog"]]
            if catalog.id not in catalog_paths:
                catalog_paths[catalog.id] = [path for path in catalog.options(data_dir)
                                             if matches(path, filter_rules.get(catalog.id, []))]
            if not any(scoped_paths(catalog_paths[catalog.id], config["scope"])):
                errors.append(f"Group {group_id}: path scope contains no indexed logos after catalog filters; check the directory, filters and catalog index")
                del groups[group_id]
        except Exception as exc:
            errors.append(f"Group {group_id}: could not read catalog: {exc}")
            del groups[group_id]
    result = {"applied": 0, "preserved": 0, "ignored": 0, "skipped": 0, "failed": 0,
              "channels": [], "configuration_errors": errors}
    channels = list(channels)
    counts = Counter(str(channel["id"]) for channel in channels)
    indices = {}
    for channel in channels:
        channel_id = str(channel["id"])
        group_id = str(channel["group_id"]) if channel.get("group_id") is not None else None
        config = groups.get(group_id)
        if config is None:
            if (channel_id not in manual_rows and channel_id not in ignored_channels) or group_id not in enabled_groups:
                continue
            config = enabled_groups[group_id]
        detail = {"channel": channel_id, "name": channel.get("name", ""), "group": group_id}
        try:
            if counts[channel_id] > 1:
                reason = "duplicate_channel"
            elif channel_id in ignored_channels or any(channel_matches(channel.get("name", ""), rule) for rule in ignore_patterns):
                reason = "ignored"
            elif channel_id in manual_rows:
                reason = manual_disposition(manual_rows[channel_id])
            elif channel.get("logo_id") is not None and not config["replace"]:
                reason = "existing_logo"
            else:
                catalog = catalog_by_id[config["catalog"]]
                selected = tuple(i for i, rule in enumerate(hints) if channel_matches(channel["name"], rule))

                def attempt(selection):
                    key = (catalog.id, config["scope"], config["generic_fallback"], selection)
                    if key not in indices:
                        paths = catalog_paths[catalog.id]
                        if selection is not None:
                            path_rules = [hints[i][3] for i in selection]
                            paths = [path for path in paths if matches(path, path_rules)]
                        indices[key] = (build_name_index(paths, catalog, config["scope"]),
                                        build_callsign_index(paths, catalog, config["scope"]),
                                        build_network_index(paths, catalog, config["scope"]) if config["generic_fallback"] else None,
                                        build_station_name_index(paths, catalog, config["scope"]))
                    name_index, callsign_index, network_index, station_name_index = indices[key]
                    return match_channel(channel["name"], config, name_index, callsign_index, catalog, network_index,
                                         channel.get("guide_id"), station_name_index)

                match = attempt(selected) if selected else None
                if match is None or match["reason"] is not None:
                    match = attempt(None)
                detail["method"] = match["method"]
                if match.get("score") is not None:
                    detail["score"] = match["score"]
                if match.get("candidates"):
                    detail["candidates"] = [{**candidate, "path": f"{catalog.id}:{candidate['path']}"}
                                            for candidate in match["candidates"]]
                    if match.get("candidates_truncated"):
                        detail["candidates_truncated"] = match["candidates_truncated"]
                reason = match["reason"]
                if reason is None:
                    identity = f"{catalog.id}:{match['path']}"
                    with catalog.resolve(data_dir, match["path"]) as image:
                        reason = assign(channel_id, group_id, channel["name"], channel.get("guide_id"), config, identity, image)
                    if reason is None:
                        detail["logo"] = identity
            if reason is None:
                result["applied"] += 1
                detail["status"] = "applied"
            elif reason in {"manual_mapping", "ignored"}:
                result["preserved" if reason == "manual_mapping" else "ignored"] += 1
                detail.update(status="success", outcome="manual_mapping_preserved" if reason == "manual_mapping" else "ignored")
            else:
                result["skipped"] += 1
                detail.update(status="skipped", reason=reason)
        except Exception as exc:
            result["failed"] += 1
            detail.update(status="failed", reason=str(exc))
        result["channels"].append(detail)
    return result
