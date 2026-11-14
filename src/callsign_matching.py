"""Conservative station-specific call-sign matching."""

from collections import defaultdict
import re

from .catalog_scope import scoped_paths
from .variants import select_variant
from .name_matching import normalize_name
from .candidates import candidate_details
from .catalogs.matching import matching_adapter

# Only station-looking, uppercase channel tokens are extracted. A call sign
# alone does not establish station identity outside station-specific paths.
_CHANNEL_CALLSIGN = re.compile(r"(?<![A-Za-z0-9])([KW][A-Z]{2,3}|C[A-Z]{3})(?:-(?:TV|LD|CD|DT))?(?![A-Za-z0-9])")
def build_callsign_index(paths, catalog_id, scope=""):
    """Index provider-recognized station call signs within the scope."""
    index = defaultdict(set)
    adapter = matching_adapter(catalog_id)
    for value, path in scoped_paths(paths, scope):
        for token in adapter.callsigns(path):
            index[token].add(value)
    return {token: tuple(sorted(values)) for token, values in index.items()}


def build_station_name_index(paths, catalog_id, scope=""):
    """Index exact local station names when the filename includes a call sign."""
    index = defaultdict(set)
    adapter = matching_adapter(catalog_id)
    for value, path in scoped_paths(paths, scope):
        name = adapter.station_name(path)
        if name:
            key = normalize_name(name)
            if key:
                index[key].add(value)
    return {key: tuple(sorted(values)) for key, values in index.items()}


def match_callsign(channel_name, index, variant="strict", catalog_id=None):
    """Match one uppercase call sign, or return a reason to skip the channel."""
    tokens = set(_CHANNEL_CALLSIGN.findall(channel_name))
    if not tokens:
        return {"path": None, "reason": "no_callsign"}
    if len(tokens) > 1:
        return {"path": None, "reason": "ambiguous_callsign"}
    candidates = index.get(tokens.pop(), ())
    if not candidates:
        return {"path": None, "reason": "no_match"}
    selected = select_variant(candidates, variant, catalog_id)
    if selected is None:
        return {"path": None, "reason": "ambiguous", **candidate_details(candidates)}
    return {"path": selected, "reason": None}
