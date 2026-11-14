"""Conservative exact matching against catalog-relative logo paths."""

from collections import defaultdict
import unicodedata
import re

from .catalog_scope import scoped_paths
from .variants import select_variant
from .candidates import candidate_details
from .catalogs.matching import matching_adapter

_GENERIC_SUFFIXES = ("television", "channel", "network")


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


def build_name_index(paths, catalog_id, scope=""):
    """Index paths within one directory scope, preserving duplicate variants.

    A scope matches whole path components, never a similarly prefixed directory.
    Callers should pass paths from the selected catalog's existing index.
    """
    index = defaultdict(set)
    aliases = defaultdict(set)
    adapter = matching_adapter(catalog_id)
    for value, path in scoped_paths(paths, scope):
        name = normalize_name(adapter.filename_name(path))
        if name:
            index[name].add(value)
            alias = _without_generic_suffix(name)
            if alias:
                aliases[alias].add(value)
            for alternative in adapter.aliases(path, name):
                aliases[alternative].add(value)
    # The unnumbered name may refer to the first channel in a numbered family.
    numbered = defaultdict(set)
    for name in index:
        match = re.fullmatch(r"([^\d]+)(\d+)", name)
        if match:
            numbered[match.group(1)].add(match.group(2))
        leading = re.fullmatch(r"(\d+)([^\d]+)", name)
        if leading and len(leading.group(2)) >= 3:
            aliases[leading.group(2) + leading.group(1)].update(index[name])
    for base, numbers in numbered.items():
        if len(base) >= 3 and "1" in numbers:
            aliases[base].update(index[base + "1"])
    # Explicit names take precedence over inferred aliases.
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
        return {"path": None, "reason": "ambiguous", **candidate_details(candidates)}
    return {"path": selected, "reason": None}
