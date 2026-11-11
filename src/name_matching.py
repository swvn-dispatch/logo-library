"""Conservative exact matching against catalog-relative logo paths."""

from collections import defaultdict
import unicodedata

from .catalog_scope import scoped_paths

# TV Logos uses these country suffixes in the corresponding directories.
# Do not strip an unrecognized suffix: it may be part of a network name.
_COUNTRY_SUFFIXES = {
    "united-states": "us", "united-kingdom": "uk", "canada": "ca",
    "australia": "au", "new-zealand": "nz",
}
_VARIANTS = {"hd", "hz", "horizontal"}


def normalize_name(value, prefix=""):
    """Normalize case and punctuation while retaining digits and plus signs.

    The optional prefix is removed only at the beginning, before punctuation
    normalization. Unicode is normalized but not transliterated.
    """
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    prefix = unicodedata.normalize("NFKC", prefix).casefold().strip()
    if prefix and value.startswith(prefix):
        value = value[len(prefix):]
    value = value.replace("&", "and").replace("+", "plus")
    return "".join(char for char in value if char.isalnum())


def _filename_name(path, catalog_id):
    filename = path.stem
    if catalog_id != "tv_logos":
        return filename
    parts = filename.split("-")
    directories = path.parts
    if len(directories) >= 3 and directories[0] == "countries":
        suffix = _COUNTRY_SUFFIXES.get(directories[1].casefold())
        if suffix and len(parts) > 1 and parts[-1].casefold() == suffix:
            parts.pop()
    while len(parts) > 1 and parts[-1].casefold() in _VARIANTS:
        parts.pop()
    return "-".join(parts)


def build_name_index(paths, catalog_id, scope=""):
    """Index paths within one directory scope, preserving duplicate variants.

    A scope matches whole path components, never a similarly prefixed directory.
    Callers should pass paths from the selected catalog's existing index.
    """
    index = defaultdict(set)
    for value, path in scoped_paths(paths, scope):
        name = normalize_name(_filename_name(path, catalog_id))
        if name:
            index[name].add(value)
    return {name: tuple(sorted(values)) for name, values in index.items()}


def match_name(channel_name, index, prefix=""):
    """Return a unique path or a reason suitable for reporting a skip."""
    key = normalize_name(channel_name, prefix)
    candidates = index.get(key, ()) if key else ()
    if not candidates:
        return {"path": None, "reason": "no_match"}
    if len(candidates) != 1:
        return {"path": None, "reason": "ambiguous"}
    return {"path": candidates[0], "reason": None}
