"""Validation for group-scoped automatic matching configuration."""

from collections import Counter
from copy import deepcopy
from pathlib import PurePosixPath
import re

from .mappings import automatic_ignored_channels


def configuration_snapshot(settings, group_options):
    """Return matching configuration, with defaults and safe group labels."""
    def scalar(value):
        return value if value is None or isinstance(value, (str, int, float, bool)) else "<invalid>"

    labels = {str(option["value"]): option["label"] for option in group_options}
    rows = settings.get("automatic_groups", [])
    groups = []
    if isinstance(rows, list):
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                groups.append({"row": index, "invalid": True})
                continue
            group_id = scalar(row.get("group"))
            groups.append({"row": index, "group": group_id, "group_name": labels.get(str(group_id)),
                           "strategy": scalar(row.get("strategy")), "scope": scalar(row.get("scope")),
                           "replace": scalar(row.get("replace"))})
    else:
        groups = "<invalid>"

    rules = settings.get("automatic_prefix_rules", [])
    if isinstance(rules, list):
        rules = [{key: scalar(row.get(key)) for key in ("group", "mode", "prefix")}
                 if isinstance(row, dict) else {"invalid": True} for row in rules]
    else:
        rules = "<invalid>"
    filters = settings.get("catalog_filters", [])
    if isinstance(filters, list):
        filters = [{key: scalar(row.get(key)) for key in ("mode", "text", "catalog")}
                   if isinstance(row, dict) else {"invalid": True} for row in filters]
    else:
        filters = "<invalid>"
    try:
        ignored = sorted(automatic_ignored_channels(settings), key=int)
    except ValueError:
        ignored = "<invalid>"
    return {
        "snapshot": "start_of_run",
        "groups": groups,
        "ignored_channels": ignored,
        "advanced": {
            "prefix": scalar(settings.get("automatic_prefix", "")),
            "prefix_mode": scalar(settings.get("automatic_prefix_mode", "literal")),
            "prefix_rules": rules,
            "fuzzy_threshold": scalar(settings.get("automatic_threshold", 90)),
            "variant_preference": scalar(settings.get("automatic_variant", "strict")),
            "generic_network_fallback": scalar(settings.get("automatic_generic_fallback", False)),
            "guide_id_signals": scalar(settings.get("automatic_guide_signals", False)),
        },
        "catalog_filters": filters,
    }


def compile_groups(rows, group_ids, catalog_ids, settings=None):
    """Return valid enabled settings keyed by stable group ID and row errors.

    Duplicate groups are all rejected, rather than picking a potentially unsafe
    replacement policy based on row order. Matching is deliberately separate.
    """
    if not isinstance(rows, list):
        return {}, ["Group settings must be a list"]
    settings = settings if settings is not None else {}
    catalog_ids = set(catalog_ids)
    prefix_rows = settings.get("automatic_prefix_rules", [])
    if not isinstance(prefix_rows, list):
        return {}, ["Prefix rules must be a list"]
    prefix_counts = Counter(str(row["group"]) for row in prefix_rows if isinstance(row, dict)
                            and row.get("group") not in (None, ""))
    prefix_rules = {str(row["group"]): row for row in prefix_rows if isinstance(row, dict)
                    and row.get("group") not in (None, "")}
    counts = Counter(str(row["group"]) for row in rows if isinstance(row, dict)
                     and row.get("group") not in (None, ""))
    groups = {str(group) for group in group_ids}
    compiled = {}
    errors = []
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
            if len(catalog_ids) != 1:
                raise ValueError("Automatic matching requires exactly one catalog")
            catalog_id = next(iter(catalog_ids))
            scope = row.get("scope") or ""
            if not isinstance(scope, str) or "\\" in scope or "\x00" in scope:
                raise ValueError("Invalid path scope")
            path = PurePosixPath(scope)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Path scope must be a catalog-relative directory")
            replace = row.get("replace")
            if replace not in (None, True, False) or not isinstance(replace, (bool, type(None))):
                raise ValueError("Replace existing logos must be a boolean")
            if prefix_counts[group] > 1:
                raise ValueError("Group has more than one prefix rule")
            rule = prefix_rules.get(group)
            prefix = rule.get("prefix", "") if rule else settings.get("automatic_prefix", "")
            if not isinstance(prefix, str):
                raise ValueError("Name prefix must be text")
            prefix_mode = (rule.get("mode") or "literal") if rule else (settings.get("automatic_prefix_mode") or "literal")
            if prefix_mode not in {"literal", "regex"}:
                raise ValueError("Unknown prefix mode")
            if prefix_mode == "regex":
                try:
                    re.compile(prefix, re.IGNORECASE)
                except re.error as exc:
                    raise ValueError(f"Invalid prefix regex: {exc}") from exc
            variant = settings.get("automatic_variant", "strict") or "strict"
            if variant not in {"strict", "standard"}:
                raise ValueError("Unknown variant preference")
            generic = settings.get("automatic_generic_fallback", False)
            if not isinstance(generic, bool):
                raise ValueError("Generic network fallback must be a boolean")
            guide = settings.get("automatic_guide_signals", False)
            if not isinstance(guide, bool):
                raise ValueError("Guide ID signal must be a boolean")
            threshold = settings.get("automatic_threshold", 90)
            if strategy == "fuzzy" and (isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 100):
                raise ValueError("Fuzzy threshold must be between 0 and 100")
            compiled[group] = {"strategy": strategy, "catalog": catalog_id,
                               "scope": "" if str(path) == "." else str(path), "replace": bool(replace),
                               "prefix": prefix, "prefix_mode": prefix_mode,
                               "variant": variant, "generic_fallback": generic, "guide_signals": guide,
                               "threshold": threshold,
                               "catalog_filters": deepcopy(settings.get("catalog_filters", []))}
        except ValueError as exc:
            errors.append(f"Row {index}: {exc}")
    return compiled, errors
