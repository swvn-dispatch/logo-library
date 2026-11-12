"""Conservative exact matching against catalog-relative logo paths."""

from collections import defaultdict
import unicodedata
import re

from .catalog_scope import scoped_paths
from .variants import select_variant

# TV Logos uses these country suffixes in the corresponding directories.
# Do not strip an unrecognized suffix: it may be part of a network name.
_COUNTRY_SUFFIXES = {
    "united-states": "us", "united-kingdom": "uk", "canada": "ca",
    "australia": "au", "new-zealand": "nz",
}
_VARIANTS = {"hd", "hz", "horizontal"}
_GENERIC_SUFFIXES = ("television", "channel", "network")
# Exact alternate branding for filenames in TV Logos. These are scoped to the
# catalog's country directory, never applied to another catalog or country.
_TV_LOGOS_ALIASES = {
    ("united-kingdom", "4more"): ("more4",),
    ("united-states", "eentertainment"): ("e",),
    ("united-states", "cspan1"): ("cspan",),
}


def _without_generic_suffix(name):
    for suffix in _GENERIC_SUFFIXES:
        if name.endswith(suffix) and len(name) - len(suffix) >= 3:
            return name[:-len(suffix)]
    return None


def normalize_name(value, prefix="", prefix_mode="literal"):
    """Normalize case and punctuation while retaining digits and plus signs.

    The optional prefix is removed only at the beginning, before punctuation
    normalization. Unicode is normalized but not transliterated.
    """
    value = unicodedata.normalize("NFKC", value).strip()
    if prefix and prefix_mode == "regex":
        match = re.match(prefix, value, re.IGNORECASE)
        if match:
            value = value[match.end():]
    else:
        value = value.casefold()
        prefix = unicodedata.normalize("NFKC", prefix).casefold().strip()
        if prefix and value.startswith(prefix):
            value = value[len(prefix):]
    value = value.casefold()
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
    aliases = defaultdict(set)
    for value, path in scoped_paths(paths, scope):
        name = normalize_name(_filename_name(path, catalog_id))
        if name:
            index[name].add(value)
            alias = _without_generic_suffix(name)
            if alias:
                aliases[alias].add(value)
            if catalog_id == "tv_logos" and len(path.parts) >= 3 and path.parts[0] == "countries":
                for alternative in _TV_LOGOS_ALIASES.get((path.parts[1], name), ()):
                    aliases[alternative].add(value)
    # Explicit names take precedence over inferred descriptive suffix aliases.
    for key, values in aliases.items():
        if key not in index:
            index[key].update(values)
    return {name: tuple(sorted(values)) for name, values in index.items()}


def match_name(channel_name, index, prefix="", prefix_mode="literal", variant="strict", catalog_id=None):
    """Return a unique path or a reason suitable for reporting a skip."""
    key = normalize_name(channel_name, prefix, prefix_mode)
    candidates = index.get(key, ()) if key else ()
    if not candidates and key:
        shorter = _without_generic_suffix(key)
        candidates = index.get(shorter, ()) if shorter else ()
    if not candidates:
        return {"path": None, "reason": "no_match"}
    selected = select_variant(candidates, variant, catalog_id)
    if selected is None:
        return {"path": None, "reason": "ambiguous"}
    return {"path": selected, "reason": None}
