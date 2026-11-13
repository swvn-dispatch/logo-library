"""Conservative station-specific call-sign matching."""

from collections import defaultdict
import re

from .catalog_scope import scoped_paths
from .variants import select_variant
from .name_matching import normalize_name
from .candidates import candidate_details

# Only station-looking, uppercase channel tokens are extracted. A call sign
# alone does not establish station identity outside station-specific paths.
_CHANNEL_CALLSIGN = re.compile(r"(?<![A-Za-z0-9])([KW][A-Z]{2,3}|C[A-Z]{3})(?:-(?:TV|LD|CD|DT))?(?![A-Za-z0-9])")
_FILE_TOKEN = re.compile(r"[a-z0-9]+")
_US_LOCAL = ("countries", "united-states", "us-local")
_CA_LOCAL = ("countries", "canada", "local")


def build_callsign_index(paths, catalog_id, scope=""):
    """Index whole filename tokens in station-specific TV Logos directories.

    Even a broad user scope cannot admit generic catalog paths. Call-sign
    token matches elsewhere, including generic Canadian CITY filenames, are not
    verified enough to assign automatically.
    """
    index = defaultdict(set)
    for value, path in scoped_paths(paths, scope):
        if catalog_id != "tv_logos" or path.parts[:3] not in (_US_LOCAL, _CA_LOCAL):
            continue
        for token in set(_FILE_TOKEN.findall(path.stem.lower())):
            pattern = r"[kw][a-z]{2,3}" if path.parts[:3] == _US_LOCAL else r"c[a-z]{3}"
            if re.fullmatch(pattern, token):
                index[token.upper()].add(value)
    return {token: tuple(sorted(values)) for token, values in index.items()}


def build_station_name_index(paths, catalog_id, scope=""):
    """Index exact local station names when the filename includes a call sign."""
    index = defaultdict(set)
    for value, path in scoped_paths(paths, scope):
        region = path.parts[:3]
        if catalog_id != "tv_logos" or region not in (_US_LOCAL, _CA_LOCAL):
            continue
        parts = path.stem.lower().split("-")
        if parts and parts[-1] in {"us", "ca"}:
            parts.pop()
        if parts and parts[-1] in {"hd", "hz", "horizontal"}:
            continue
        pattern = r"[kw][a-z]{2,3}" if region == _US_LOCAL else r"c[a-z]{3}"
        if len(parts) > 1 and re.fullmatch(pattern, parts[-1]):
            key = normalize_name("-".join(parts[:-1]))
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
