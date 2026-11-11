"""Conservative US local-station call-sign matching."""

from collections import defaultdict
import re

from .catalog_scope import scoped_paths
from .variants import select_variant

# Only station-looking, uppercase channel tokens are extracted. A call sign
# alone does not establish station identity outside station-specific paths.
_CHANNEL_CALLSIGN = re.compile(r"(?<![A-Za-z0-9])([KW][A-Z]{2,3})(?:-(?:TV|LD|CD|DT))?(?![A-Za-z0-9])")
_FILE_TOKEN = re.compile(r"[a-z0-9]+")
_US_LOCAL = ("countries", "united-states", "us-local")


def build_callsign_index(paths, catalog_id, scope=""):
    """Index whole filename tokens, restricted to TV Logos US local stations.

    Even a broad user scope cannot admit generic catalog paths. Call-sign
    token matches elsewhere, including Canadian CITY, are not verified enough
    to assign automatically.
    """
    index = defaultdict(set)
    for value, path in scoped_paths(paths, scope):
        if catalog_id != "tv_logos" or path.parts[:3] != _US_LOCAL:
            continue
        for token in set(_FILE_TOKEN.findall(path.stem.lower())):
            if re.fullmatch(r"[kw][a-z]{2,3}", token):
                index[token.upper()].add(value)
    return {token: tuple(sorted(values)) for token, values in index.items()}


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
        return {"path": None, "reason": "ambiguous"}
    return {"path": selected, "reason": None}
