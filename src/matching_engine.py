"""Combine scoped evidence without guessing on conflicting candidates."""

from pathlib import PurePosixPath
import re
import html
from collections import defaultdict

from .catalog_scope import scoped_paths
from .callsign_matching import match_callsign
from .fuzzy_matching import match_fuzzy
from .name_matching import _filename_name, match_name, normalize_name
from .variants import select_variant

_STATION_TOKEN = r"(?:[KW][A-Z]{2,3}|C[A-Z]{3})"


def _tokens(value):
    tokens = re.findall(r"[^\W\d_]+|\d+|[+&]", value.casefold())
    return tuple("and" if token == "&" else "plus" if token == "+" else token for token in tokens)


def build_network_index(paths, catalog_id, scope=""):
    """Index generic TV Logos network names, never station-specific folders."""
    index = defaultdict(list)
    for value, path in scoped_paths(paths, scope):
        if (catalog_id != "tv_logos" or len(path.parts) < 3 or path.parts[0] != "countries"
                or path.parts[1] not in {"canada", "united-states", "united-kingdom"}):
            continue
        parent = path.parts[2:-1]
        if parent not in ((), ("hd",)):
            continue
        tokens = _tokens(_filename_name(path, catalog_id))
        if tokens:
            index[tokens[0]].append((tokens, value))
    return index


def _network_fallback(segments, index, variant, catalog_id):
    candidates = []
    for segment in segments:
        words = _tokens(segment)
        if len(words) < 2:
            continue
        for tokens, path in index.get(words[0], ()):
            if (len(words) > len(tokens) and words[:len(tokens)] == tokens
                    and not words[len(tokens)].isdigit()):
                candidates.append((len(tokens), path))
    if not candidates:
        return None
    length = max(size for size, _ in candidates)
    paths = {path for size, path in candidates if size == length}
    chosen = select_variant(paths, variant, catalog_id)
    return {"path": chosen, "reason": None if chosen else "ambiguous", "method": "network_fallback"}


def _explicit_station(name, segments):
    """Require a standalone station component or explicit broadcast suffix."""
    return bool(
        (len(segments) > 2 and re.fullmatch(_STATION_TOKEN + r"(?:-(?:TV|LD|CD|DT))?", segments[-1].strip()))
        or re.search(r"\(" + _STATION_TOKEN + r"(?:-(?:TV|LD|CD|DT))?\)", name)
        or re.search(r"(?<![A-Za-z0-9])" + _STATION_TOKEN + r"-(?:TV|LD|CD|DT)(?![A-Za-z0-9])", name)
    )


def match_channel(name, config, name_index, callsign_index, catalog_id, network_index=None, guide_id=None):
    """Try exact evidence first; the strategy enables optional fuzzy fallback.

    Delimited components are considered independently of any country prefix or
    provider format. Two-letter region-like components and trailing station
    tokens are not treated as network names. Conflicting candidates are skipped.
    """
    prefix, mode, variant = config["prefix"], config["prefix_mode"], config["variant"]
    evidence = []
    full = match_name(name, name_index, prefix, mode, variant, catalog_id)
    if full["reason"] == "ambiguous":
        return {"path": None, "reason": "ambiguous", "method": "exact"}
    if full["path"]:
        evidence.append((full["path"], "exact", normalize_name(name, prefix, mode)))

    station = match_callsign(name, callsign_index, variant, catalog_id)
    if station["reason"] in {"ambiguous", "ambiguous_callsign"}:
        return {"path": None, "reason": station["reason"], "method": "callsign"}
    if station["path"]:
        evidence.append((station["path"], "callsign", ""))

    segments = re.split(r"\s*\|\s*|\s+[-\u2013\u2014]\s+", name)
    if config.get("guide_signals") and isinstance(guide_id, str) and guide_id:
        guide = match_callsign(html.unescape(guide_id).upper(), callsign_index, variant, catalog_id)
        if guide["path"]:
            station_tokens = _tokens(PurePosixPath(guide["path"]).stem)
            # Guide IDs are unstable. Only use station-specific filenames when
            # the channel name independently agrees on the network name.
            network = station_tokens[0] if station_tokens else ""
            corroborated = len(network) >= 3 and any(_tokens(segment)[:1] == (network,) for segment in segments)
            if corroborated:
                if station["path"] and station["path"] != guide["path"]:
                    return {"path": None, "reason": "conflicting_matches", "method": "guide_callsign"}
                if not station["path"]:
                    station = guide
                    evidence.append((guide["path"], "guide_callsign", ""))
    if len(segments) > 1:
        for segment in segments:
            key = normalize_name(segment)
            if len(key) < 2 or re.fullmatch(r"[A-Za-z]{2}", segment.strip()):
                continue
            if len(segments) > 2 and re.fullmatch(r"(?:[KW][A-Z]{2,3}|C[A-Z]{3})(?:-(?:TV|LD|CD|DT))?", segment.strip()):
                continue
            match = match_name(segment, name_index, variant=variant, catalog_id=catalog_id)
            if match["reason"] == "ambiguous":
                return {"path": None, "reason": "ambiguous", "method": "name_segment"}
            if match["path"]:
                evidence.append((match["path"], "name_segment", key))

    paths = {path for path, _, _ in evidence}
    if len(paths) > 1 and station["path"]:
        # A station-specific file may refine an exact generic city logo, but
        # only when its filename begins with every competing exact name.
        station_key = normalize_name(PurePosixPath(station["path"]).stem)
        if all(path == station["path"] or (key and station_key.startswith(key))
               for path, _, key in evidence):
            paths = {station["path"]}
    if len(paths) > 1:
        return {"path": None, "reason": "conflicting_matches", "method": "combined"}
    if paths:
        path = next(iter(paths))
        if any(p == path and method == "guide_callsign" for p, method, _ in evidence):
            method = "guide_callsign"
        elif config["strategy"] == "callsign" and station["path"] == path:
            method = "callsign"
        else:
            method = next(method for p, method, _ in evidence if p == path)
        return {"path": path, "reason": None, "method": method}

    if (config.get("generic_fallback") and network_index and station["reason"] == "no_match"
            and _explicit_station(name, segments)):
        fallback = _network_fallback(segments, network_index, variant, catalog_id)
        if fallback:
            return fallback

    # An unmatched station token is not evidence that a generic network logo
    # represents that station, even when its name has a high fuzzy score.
    if config["strategy"] == "fuzzy" and station["reason"] == "no_callsign":
        result = match_fuzzy(name, name_index, config["threshold"], prefix, mode, variant, catalog_id)
        return {**result, "method": "fuzzy"}
    return {"path": None, "reason": "no_match", "method": "combined"}
