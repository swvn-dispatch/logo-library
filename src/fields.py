"""Build native Dispatcharr settings fields from the current catalog."""

import logging
from pathlib import PurePosixPath

from . import catalogs
from .filters import MATCH_TYPES, catalog_filter_rules, matches

logger = logging.getLogger(__name__)


def _valid_text(value):
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def make_fields(data_dir, settings, channels, groups=()):
    rules, filter_errors = catalog_filter_rules(settings.get("catalog_filters", []), catalogs.CATALOGS)
    logo_options = []
    all_logos = {}
    directories = set()
    for catalog in catalogs.CATALOGS:
        try:
            for path in catalog.options(data_dir):
                value, label = f"{catalog.id}:{path}", f"{catalog.label} / {path}"
                if _valid_text(path) and _valid_text(value) and _valid_text(label):
                    all_logos[value] = label
                    if matches(path, rules.get(catalog.id, [])):
                        logo_options.append({"value": value, "label": label})
                        if len(catalogs.CATALOGS) == 1:
                            directories.update(str(parent) for parent in PurePosixPath(path).parents if str(parent) != ".")
                else:
                    logger.warning("Skipping invalid logo option from catalog %s", catalog.id)
        except (OSError, ValueError):
            logger.warning("Could not list logos from catalog %s", catalog.id, exc_info=True)
        except Exception:
            logger.exception("Catalog %s failed to list logos", catalog.id)
    channel_options = list(channels)
    channel_ids = {option["value"] for option in channel_options}
    logo_ids = {option["value"] for option in logo_options}
    rows = settings.get("mappings", [])
    if not isinstance(rows, list):
        rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        channel, logo = row.get("channel"), row.get("logo")
        if channel not in (None, "") and str(channel) not in channel_ids:
            channel_ids.add(str(channel))
            channel_options.append({"value": str(channel), "label": f"Missing channel (ID {channel})"})
        if _valid_text(logo) and logo and logo not in logo_ids:
            logo_ids.add(logo)
            try:
                catalog, path = catalogs.parse_logo(logo)
                canonical = f"{catalog.id}:{path}"
                label = all_logos.get(canonical, f"Missing: {logo}")
            except ValueError:
                label = f"Missing: {logo}"
            logo_options.append({"value": logo, "label": label})
    group_options = list(groups)
    group_ids = {option["value"] for option in group_options}
    group_rows = settings.get("automatic_groups", [])
    has_legacy_callsign = isinstance(group_rows, list) and any(
        isinstance(row, dict) and row.get("strategy") == "callsign" for row in group_rows
    )
    scope_options = [{"value": ".", "label": "Entire catalog"}] + [
        {"value": path, "label": path} for path in sorted(directories, key=str.casefold)
    ]
    saved_scopes = {row.get("scope") for row in group_rows if isinstance(row, dict)
                    and isinstance(row.get("scope"), str) and row.get("scope") not in ("", ".")} if isinstance(group_rows, list) else set()
    scope_options.extend({"value": path, "label": f"Unavailable or filtered: {path}"}
                         for path in sorted(saved_scopes - directories))
    unavailable_groups = set()
    if isinstance(group_rows, list):
        for row in group_rows:
            if not isinstance(row, dict):
                continue
            group = row.get("group")
            if group not in (None, "") and str(group) not in group_ids:
                unavailable_groups.add(str(group))
    return [
        {"id": "instructions", "type": "info", "label": "Catalog and mappings",
         "description": "After a catalog is downloaded, refreshed, or indexed, it is recommended to click Reload plugin."},
        {"id": "manual_assignment", "type": "section", "label": "Manual assignment", "collapsed": False},
        {"id": "manual_instructions", "type": "info", "section": "manual_assignment",
         "description": "Save mappings before running Manual Match. Removing a mapping does not remove the channel's assigned logo."},
        {"id": "mappings", "type": "table", "section": "manual_assignment", "label": "Channel logo mappings", "default": [],
         "columns": [
             {"id": "channel", "label": "Channel", "type": "select", "options": channel_options},
             {"id": "logo", "label": "Logo path", "type": "select", "options": logo_options},
         ]},
        {"id": "automatic_assignment", "type": "section", "label": "Automatic assignment", "collapsed": False},
        {"id": "automatic_coming_soon", "type": "info", "section": "automatic_assignment",
         "description": "Add one row for each group to match and save before running Auto Match. Groups without an enabled row are skipped. Saved manual mappings take priority."},
        {"id": "automatic_group_help", "type": "info", "section": "automatic_assignment",
         "description": "Channel group: select a group currently used by a channel."},
        {"id": "automatic_strategy_help", "type": "info", "section": "automatic_assignment",
         "description": "Strategy: use Standard. Choose Standard + fuzzy only if Standard misses channels and you are willing to review possible false matches. Disabled skips the group."},
        {"id": "automatic_scope_help", "type": "info", "section": "automatic_assignment",
         "description": "Path scope: select a catalog directory, or leave blank to search all filtered logos. Unavailable or filtered saved paths cannot be matched."},
        {"id": "automatic_replace_help", "type": "info", "section": "automatic_assignment",
         "description": "Replace: allow matching to replace a channel's effective logo. Manual mappings always take priority."},
        *([{"id": "automatic_missing_groups", "type": "info", "section": "automatic_assignment",
            "label": "Unavailable saved groups", "description": "These saved group IDs are not currently used by channels: " + ", ".join(sorted(unavailable_groups)) + ". They are not selectable or active."}] if unavailable_groups else []),
        {"id": "automatic_groups", "type": "table", "section": "automatic_assignment", "label": "Group matching settings", "default": [],
         "columns": [
             {"id": "group", "label": "Channel group", "type": "select", "options": group_options},
             {"id": "strategy", "label": "Strategy", "type": "select", "options": [
                 {"value": "disabled", "label": "Disabled"},
                 {"value": "exact", "label": "Standard"},
                 *([{"value": "callsign", "label": "Standard (legacy station hint)"}] if has_legacy_callsign else []),
                 {"value": "fuzzy", "label": "Standard + fuzzy"},
             ]},
             # Restore the catalog column and selection logic when more catalogs are added.
             # {"id": "catalog", "label": "Catalog", "type": "select", "options": [...]},
             {"id": "scope", "label": "Path scope", "type": "select", "options": scope_options},
             {"id": "replace", "label": "Replace", "type": "boolean"},
         ]},
        {"id": "automatic_advanced", "type": "section", "label": "Advanced matching", "collapsed": True},
        {"id": "automatic_prefix", "type": "string", "section": "automatic_advanced",
         "label": "Name prefix to remove", "default": "",
         "description": "Optional prefix removed from the start of channel names."},
        {"id": "automatic_prefix_mode", "type": "select", "section": "automatic_advanced",
         "label": "Prefix mode", "default": "literal", "options": [
             {"value": "literal", "label": "Literal"}, {"value": "regex", "label": "Regex"}],
         "description": "Regex is matched at the start of the name. Avoid patterns with excessive backtracking."},
        *([{"id": "automatic_prefix_rules", "type": "table", "section": "automatic_advanced",
         "label": "Group-specific name prefixes", "default": [], "columns": [
             {"id": "group", "label": "Channel group", "type": "select", "options": group_options},
             {"id": "mode", "label": "Mode", "type": "select", "options": [
                 {"value": "literal", "label": "Literal"}, {"value": "regex", "label": "Regex"}]},
             {"id": "prefix", "label": "Prefix", "type": "string"},
         ]}, {"id": "automatic_prefix_help", "type": "info", "section": "automatic_advanced",
         "description": "Previously saved group prefix rules still override the shared prefix. Remove all rows to use the shared prefix for every group."}] if settings.get("automatic_prefix_rules") else []),
        {"id": "automatic_threshold", "type": "number", "section": "automatic_advanced",
         "label": "Fuzzy threshold (%)", "default": 90,
         "description": "Used by all Standard + fuzzy groups. Scores must be strictly above this value; 100 cannot match."},
        {"id": "automatic_variant", "type": "select", "section": "automatic_advanced",
         "label": "Logo variant preference", "default": "strict", "options": [
             {"value": "strict", "label": "Skip ambiguous variants"},
             {"value": "standard", "label": "Prefer standard variant"}],
         "description": "Prefer standard selects an unmarked logo only when all candidates belong to the same recognized HD or horizontal variant family; other ties are skipped."},
        {"id": "automatic_generic_fallback", "type": "boolean", "section": "automatic_advanced",
         "label": "Allow generic network logos", "default": False,
         "description": "For unmatched channels with an explicit station call sign, allow an exact network name to stand in for the station. This may assign the same network logo to multiple cities; manual mappings still take priority."},
        {"id": "automatic_guide_signals", "type": "boolean", "section": "automatic_advanced",
         "label": "Use guide IDs as a station hint", "default": False,
         "description": "Use a station call sign from the guide ID only when the channel name agrees on the network. Guide IDs can be stale or change; network agreement cannot verify the city."},
        {"id": "catalog_filters_section", "type": "section", "label": "Catalog filters", "collapsed": True},
        {"id": "catalog_filter_instructions", "type": "info", "section": "catalog_filters_section",
         "description": "Filters match full paths without regard to case. They limit logo choices, Auto Match scopes and candidates. Save and reload to update choices. Saved manual mappings remain available."},
        *([{"id": "catalog_filter_errors", "type": "info", "section": "catalog_filters_section",
            "label": "Filter errors", "description": " ".join(filter_errors) + " Auto Match will not run until these are corrected."}] if filter_errors else []),
        {"id": "catalog_filters", "type": "table", "section": "catalog_filters_section", "label": "Filters", "default": [],
         "columns": [
             # Add a catalog select when multiple catalogs are available in the UI.
             {"id": "mode", "label": "Mode", "type": "select", "options": [
                 {"value": f"{operation}_{kind}", "label": f"{operation.title()} {kind.replace('_', ' ')}"}
                 for operation in ("include", "exclude") for kind in MATCH_TYPES
             ]},
             {"id": "text", "label": "Text", "type": "string"},
         ]},
    ]
