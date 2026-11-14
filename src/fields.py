"""Build native Dispatcharr settings fields from the current catalog."""

import logging
from pathlib import PurePosixPath

from . import catalogs
from .channel_patterns import compile_patterns
from .filters import MATCH_TYPES, catalog_filter_rules, matches
from .mappings import automatic_ignored_channels
from .scheduling import parse_schedule

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
    _, hint_errors = compile_patterns(settings.get("automatic_channel_hints", []), hints=True)
    _, ignore_errors = compile_patterns(settings.get("automatic_ignore_patterns", []))
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
    ignore_options = list(channel_options)
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
            channel_options.append({"value": str(channel), "label": "Missing channel"})
        if _valid_text(logo) and logo and logo not in logo_ids:
            logo_ids.add(logo)
            try:
                catalog, path = catalogs.parse_logo(logo)
                canonical = f"{catalog.id}:{path}"
                label = all_logos.get(canonical, f"Missing: {logo}")
            except ValueError:
                label = f"Missing: {logo}"
            logo_options.append({"value": logo, "label": label})
    try:
        ignored_ids = sorted(automatic_ignored_channels(settings), key=int)
    except ValueError:
        ignored_ids = []
    ignore_ids = {str(option["value"]) for option in ignore_options}
    for channel_id in ignored_ids:
        if channel_id not in ignore_ids:
            ignore_options.append({"value": channel_id, "label": "Missing channel"})
    channel_labels = {str(option["value"]): option["label"] for option in channel_options}
    legacy_ignored = sorted({str(row["channel"]) for row in rows if isinstance(row, dict)
                             and row.get("ignore") is True and row.get("channel") not in (None, "")})
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
    schedule_errors = []
    for key, label in (("automatic", "Auto Match"), ("catalog", "Catalog refresh")):
        try:
            parse_schedule(settings.get(f"schedule_{key}_mode", "disabled"), settings.get(f"schedule_{key}_value", ""))
        except ValueError as exc:
            schedule_errors.append(f"{label}: {exc}.")
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
         "description": "Save mappings before running Manual Match. Removing a row does not remove the assigned logo."},
        *([{"id": "manual_legacy_ignore", "type": "info", "section": "manual_assignment",
            "label": "Previously ignored channels",
            "description": "Save these channels in Channels to ignore under Automatic assignment, then remove their old manual rows: "
            + ", ".join(channel_labels.get(channel, "Missing channel") for channel in legacy_ignored)
            + ". Those old rows never assign a logo."}] if legacy_ignored else []),
        {"id": "mappings", "type": "table", "section": "manual_assignment", "label": "Channel logo mappings", "default": [],
         "columns": [
             {"id": "channel", "label": "Channel", "type": "select", "options": channel_options},
             {"id": "logo", "label": "Logo path", "type": "select", "options": logo_options},
         ]},
        {"id": "automatic_assignment", "type": "section", "label": "Automatic assignment", "collapsed": False},
        {"id": "automatic_setup_help", "type": "info", "section": "automatic_assignment",
         "label": "Getting started",
         "description": "Add a row for each channel group you want to match. Choose a strategy and catalog folder for each group, then save your settings. Run Auto Match to assign logos and review the results for channels that were skipped or failed."},
        {"id": "automatic_group_help", "type": "info", "section": "automatic_assignment",
          "label": "Group settings",
          "description": "Group: The channel group to match."},
        {"id": "automatic_strategy_help", "type": "info", "section": "automatic_assignment",
         "description": "Strategy: Start with Standard, which uses names and station information. Standard + fuzzy also considers similar names."},
        {"id": "automatic_scope_help", "type": "info", "section": "automatic_assignment",
         "description": "Path scope: Choose a catalog folder or Entire catalog. We recommend a country folder unless the group contains channels from multiple countries. Catalog filters still apply."},
        {"id": "automatic_replace_help", "type": "info", "section": "automatic_assignment",
         "description": "Replace: Allows Auto Match to overwrite existing channel logos."},
        *([{"id": "automatic_missing_groups", "type": "info", "section": "automatic_assignment",
            "label": "Unavailable saved groups", "description": "These saved group IDs are not currently used by channels: " + ", ".join(sorted(unavailable_groups)) + ". They are not selectable or active."}] if unavailable_groups else []),
        {"id": "automatic_groups", "type": "table", "section": "automatic_assignment", "label": "Group matching settings", "default": [],
         "columns": [
             {"id": "group", "label": "Group", "type": "select", "options": group_options},
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
        {"id": "automatic_generic_fallback", "type": "boolean", "section": "automatic_assignment",
          "label": "Allow generic network logos", "default": True,
         "description": "For unmatched channels with an explicit station call sign, allow an exact network name to stand in for the station. This may assign the same network logo to multiple cities; manual mappings still take priority."},
        {"id": "automatic_ignored_channels", "type": "multiselect", "section": "automatic_assignment",
         "label": "Channels to ignore", "default": ignored_ids, "options": ignore_options,
         "description": "Auto Match will leave these channels unchanged. Manual Match can still apply an explicit manual mapping."},
        {"id": "automatic_advanced", "type": "section", "label": "Automatic assignment - Advanced", "collapsed": True},
        {"id": "automatic_advanced_help", "type": "info", "section": "automatic_advanced",
         "label": "Advanced matching",
         "description": "Use these optional settings to tune channel names, catalog preferences and matching behavior across enabled groups. Save settings before running Auto Match."},
        {"id": "automatic_pattern_help", "type": "info", "section": "automatic_advanced",
         "label": "Channel catalog hints",
         "description": "Prefer paths based on the original channel name. For example, use Starts With and CA | for the channel, then Contains and canada for the path. Path matching ignores case. Matching hints combine their paths; group scopes and catalog filters still apply. If no usable match is found, Auto Match searches the normal scope instead."},
        {"id": "automatic_ignore_pattern_help", "type": "info", "section": "automatic_advanced",
         "description": "Channel patterns to ignore: Match the original channel name to exclude channels from Auto Match. Manual Match can still assign them. Channel patterns support contains, starts with and regex, with optional case sensitivity. Avoid regex patterns with excessive backtracking."},
        {"id": "automatic_name_prefix_help", "type": "info", "section": "automatic_advanced",
         "description": "Name prefixes: Hints and ignore patterns do not remove prefixes. Use Name prefix to remove if the prefix should also be removed before matching a logo."},
        *([{"id": "automatic_pattern_errors", "type": "info", "section": "automatic_advanced",
            "label": "Pattern errors", "description": " ".join([f"Hint: {error}" for error in hint_errors] + [f"Ignore: {error}" for error in ignore_errors]) + " Auto Match will not run until these are corrected."}] if hint_errors or ignore_errors else []),
        *[{"id": field_id, "type": "table", "section": "automatic_advanced", "label": label, "default": [],
           "columns": [
               {"id": "mode", "label": "Channel match", "type": "select", "options": [
                   {"value": mode, "label": mode.replace("_", " ").title()} for mode in ("contains", "starts_with", "regex")]},
               {"id": "text", "label": "Channel pattern", "type": "string"},
               {"id": "case_sensitive", "label": "Case sensitive", "type": "boolean"},
               *([{"id": "path_mode", "label": "Path include", "type": "select", "options": [
                   {"value": mode, "label": mode.replace("_", " ").title()} for mode in MATCH_TYPES]},
                  {"id": "path_text", "label": "Path pattern", "type": "string"}] if hint else []),
           ]} for field_id, label, hint in (("automatic_channel_hints", "Channel catalog hints", True),
                                           ("automatic_ignore_patterns", "Channel patterns to ignore", False))],
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
          "label": "Logo variant preference", "default": "standard", "options": [
             {"value": "strict", "label": "Skip ambiguous variants"},
              {"value": "standard", "label": "Prefer standard variant"},
              {"value": "hd", "label": "Prefer HD variant"}],
          "description": "Preferences apply only within one recognized variant family. Prefer HD chooses the HD logo with the fewest additional variant attributes, or a standard logo if no HD variant is available. Unresolved ties are skipped."},
        {"id": "automatic_guide_signals", "type": "boolean", "section": "automatic_advanced",
          "label": "Use channel TVG ID as a station hint", "default": False,
          "description": "Use a station call sign from the channel's TVG ID, not its matched EPG entry, only when the channel name agrees on the network. The channel's override takes precedence when set. TVG IDs can be stale or change; network agreement cannot verify the city."},
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
        {"id": "scheduled_tasks", "type": "section", "label": "Scheduled Tasks", "collapsed": True},
        {"id": "scheduled_tasks_help", "type": "info", "section": "scheduled_tasks",
         "description": "Choose Disabled, Interval, or Cron for each task. Enter whole hours for Interval or five cron fields (minute hour day month weekday) for Cron. Cron uses UTC. Save settings to apply changes. Refresh does not run Auto Match."},
        *([{"id": "scheduled_tasks_errors", "type": "info", "section": "scheduled_tasks", "label": "Schedule errors", "description": " ".join(schedule_errors)}] if schedule_errors else []),
        *[field for key, label in (("automatic", "Auto Match"), ("catalog", "Catalog refresh")) for field in (
            {"id": f"schedule_{key}_mode", "type": "select", "section": "scheduled_tasks", "label": f"{label} schedule", "default": "disabled", "options": [
                {"value": "disabled", "label": "Disabled"}, {"value": "interval", "label": "Interval"}, {"value": "cron", "label": "Cron"}]},
            {"id": f"schedule_{key}_value", "type": "string", "section": "scheduled_tasks", "label": f"{label} interval or cron", "default": "", "description": "Whole hours, or a five-field UTC cron expression."},
        )],
    ]
