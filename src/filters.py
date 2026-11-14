"""Case-insensitive filters for catalog-relative logo paths."""

import re

MATCH_TYPES = ("contains", "starts_with", "exact", "regex")
MODES = tuple(f"{operation}_{kind}" for operation in ("include", "exclude") for kind in MATCH_TYPES)


def filter_snapshot(rows):
    """Return serializable saved filter settings for task results."""
    if not isinstance(rows, list):
        return "<invalid>"

    def scalar(value):
        return value if value is None or isinstance(value, (str, int, float, bool)) else "<invalid>"

    return [{key: scalar(row.get(key)) for key in ("mode", "text", "catalog")}
            if isinstance(row, dict) else {"invalid": True} for row in rows]


def catalog_filter_rules(rows, catalogs):
    """Compile filters using the same catalog defaults for settings and runs."""
    catalog_ids = {catalog.id for catalog in catalogs}
    legacy = [catalog.id for catalog in catalogs if getattr(catalog, "accepts_legacy_paths", False)]
    rules, errors = compile_filters(rows, legacy[0] if len(legacy) == 1 else None)
    for catalog_id in sorted(set(rules) - catalog_ids):
        errors.append(f"Unknown catalog in filters: {catalog_id}.")
    return rules, errors


def _compile_regex(pattern):
    """Compile a case-insensitive Python regular expression."""
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"Invalid regex: {exc}") from exc


def compile_filters(rows, default_catalog):
    """Return rules by catalog and row errors. Empty rows are ignored."""
    rules, errors = {}, []
    if not isinstance(rows, list):
        return rules, ["Filters must be a list."]
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"Row {index}: invalid filter.")
            continue
        mode, text = row.get("mode"), row.get("text")
        if not mode and not text:
            continue
        if mode not in MODES or not isinstance(text, str) or not text.strip():
            errors.append(f"Row {index}: select a mode and enter text.")
            continue
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            errors.append(f"Row {index}: text contains invalid characters.")
            continue
        operation, kind = mode.split("_", 1)
        try:
            pattern = _compile_regex(text) if kind == "regex" else text.casefold()
        except ValueError as exc:
            errors.append(f"Row {index}: {exc}.")
            continue
        catalog_id = row.get("catalog") or default_catalog
        if not isinstance(catalog_id, str) or not catalog_id:
            errors.append(f"Row {index}: select a catalog.")
            continue
        rules.setdefault(catalog_id, []).append((operation, kind, pattern))
    return rules, errors


def matches(path, rules):
    folded = path.casefold()

    def match(rule):
        _, kind, pattern = rule
        if kind == "contains":
            return pattern in folded
        if kind == "starts_with":
            return folded.startswith(pattern)
        if kind == "exact":
            return folded == pattern
        return pattern.search(path) is not None

    includes = [rule for rule in rules if rule[0] == "include"]
    excludes = [rule for rule in rules if rule[0] == "exclude"]
    return (not includes or any(match(rule) for rule in includes)) and not any(match(rule) for rule in excludes)
