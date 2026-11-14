"""Compile channel-name hints and exclusions for automatic matching."""

import re

from .filters import MATCH_TYPES, compile_filters


def compile_patterns(rows, hints=False):
    """Return compiled rows and row-specific errors."""
    if not isinstance(rows, list):
        return [], ["Rules must be a list."]
    compiled, errors = [], []
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"Row {number}: invalid rule.")
            continue
        mode, text = row.get("mode"), row.get("text")
        path_mode, path_text = row.get("path_mode"), row.get("path_text")
        sensitive = row.get("case_sensitive", False)
        if not mode and not text and not path_mode and not path_text and sensitive in (False, None):
            continue
        if mode not in ("contains", "starts_with", "regex") or not isinstance(text, str) or not text.strip():
            errors.append(f"Row {number}: select a channel mode and enter a pattern.")
            continue
        if sensitive is None:
            sensitive = False
        if not isinstance(sensitive, bool):
            errors.append(f"Row {number}: case sensitive must be a boolean.")
            continue
        try:
            text.encode("utf-8")
            pattern = re.compile(text, 0 if sensitive else re.IGNORECASE) if mode == "regex" else (text if sensitive else text.casefold())
        except (re.error, UnicodeEncodeError) as exc:
            errors.append(f"Row {number}: invalid channel pattern: {exc}.")
            continue
        path_rule = None
        if hints:
            if path_mode not in MATCH_TYPES:
                errors.append(f"Row {number}: select a catalog include mode.")
                continue
            rules, path_errors = compile_filters([{"mode": f"include_{path_mode}", "text": path_text}], "catalog")
            if path_errors:
                errors.append(f"Row {number}: {path_errors[0].removeprefix('Row 1: ')}")
                continue
            path_rule = rules["catalog"][0]
        compiled.append((mode, pattern, sensitive, path_rule))
    return compiled, errors


def channel_matches(name, rule):
    mode, pattern, sensitive, _ = rule
    if mode == "regex":
        return pattern.search(name) is not None
    name = name if sensitive else name.casefold()
    return pattern in name if mode == "contains" else name.startswith(pattern)
