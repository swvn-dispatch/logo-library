"""Validate and apply ordered channel-name cleanup rules."""

import re
import unicodedata


def cleanup_rows(settings):
    if "automatic_name_cleanup" in settings:
        return settings["automatic_name_cleanup"]
    prefix = settings.get("automatic_prefix", "")
    mode = settings.get("automatic_prefix_mode", "literal") or "literal"
    if not prefix:
        return []
    if mode == "regex" and isinstance(prefix, str):
        # Keep old regex prefixes anchored when shown in the new cleanup table.
        flags = re.match(r"^\(\?[aiLmsux]+\)", prefix)
        start = flags.end() if flags else 0
        prefix = prefix[:start] + "^(?:" + prefix[start:] + ")"
    return [{"mode": "starts_with" if mode == "literal" else mode, "text": prefix}]


def compile_cleanup(rows):
    if not isinstance(rows, list):
        return [], ["Cleanup rules must be a list."]
    result, errors = [], []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"Row {index}: invalid cleanup rule.")
            continue
        mode, text = row.get("mode"), row.get("text")
        if not mode and not text:
            continue
        if mode not in ("starts_with", "ends_with", "regex") or not isinstance(text, str) or not text.strip():
            errors.append(f"Row {index}: select a mode and enter text.")
            continue
        try:
            text.encode("utf-8")
            if mode == "regex":
                re.compile(text, re.IGNORECASE)
        except (re.error, UnicodeEncodeError) as exc:
            errors.append(f"Row {index}: invalid pattern: {exc}.")
            continue
        result.append({"mode": mode, "text": text})
    return result, errors


def clean_channel_name(value, rules):
    """Remove the first matching rule's text, once, without changing case."""
    value = unicodedata.normalize("NFKC", value).strip()
    for rule in rules:
        mode, text = rule["mode"], rule["text"]
        if mode == "regex":
            match = re.search(text, value, re.IGNORECASE)
        else:
            text = unicodedata.normalize("NFKC", text).strip()
            pattern = re.escape(text)
            match = re.search(("^" + pattern) if mode == "starts_with" else (pattern + "$"), value, re.IGNORECASE)
        if match:
            return value[:match.start()] + value[match.end():]
    return value
