"""Combine scoped evidence without guessing on conflicting candidates."""

from pathlib import PurePosixPath
import re
import html
from collections import defaultdict

from .catalog_scope import scoped_paths
from .callsign_matching import match_callsign
from .fuzzy_matching import match_fuzzy
from .name_matching import _filename_name, match_name, normalize_name
from .name_cleanup import clean_channel_name
from .variants import select_variant
from .candidates import candidate_details

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
    return {"path": chosen, "reason": None if chosen else "ambiguous", "method": "network_fallback",
            **(candidate_details(paths) if chosen is None else {})}


def _explicit_station(name, segments):
    """Require a standalone station component or explicit broadcast suffix."""
    return bool(
        (len(segments) > 2 and re.fullmatch(_STATION_TOKEN + r"(?:-(?:TV|LD|CD|DT))?", segments[-1].strip()))
        or re.search(r"\(" + _STATION_TOKEN + r"(?:-(?:TV|LD|CD|DT))?\)", name)
        or re.search(r"(?<![A-Za-z0-9])" + _STATION_TOKEN + r"-(?:TV|LD|CD|DT)(?![A-Za-z0-9])", name)
    )


def match_channel(name, config, name_index, callsign_index, catalog_id, network_index=None, guide_id=None,
                  station_name_index=None):
    """Try exact evidence first; the strategy enables optional fuzzy fallback.

    Delimited components are considered independently of any country prefix or
    provider format. Two-letter region-like components and trailing station
    tokens are not treated as network names. Conflicting candidates are skipped.
    """
    if config.get("name_cleanup"):
        name = clean_channel_name(name, config["name_cleanup"])
    prefix, mode, variant = config["prefix"], config["prefix_mode"], config["variant"]
    evidence = []
    full = match_name(name, name_index, prefix, mode, variant, catalog_id)
    if full["reason"] == "ambiguous":
        return {**full, "method": "exact"}
    if full["path"]:
        evidence.append((full["path"], "exact", normalize_name(name, prefix, mode)))

    station = match_callsign(name, callsign_index, variant, catalog_id)
    if station["reason"] in {"ambiguous", "ambiguous_callsign"}:
        return {**station, "method": "callsign"}
    if station["path"]:
        evidence.append((station["path"], "callsign", ""))

    segments = re.split(r"\s*\|\s*|\s+[-\u2013\u2014]\s+|:\s+", name)
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
        for segment_number, segment in enumerate(segments):
            segment = re.sub(r"\s+\(" + _STATION_TOKEN + r"(?:-(?:TV|LD|CD|DT))?\)\s*$", "", segment)
            key = normalize_name(segment)
            if not key or (segment_number == 0 and re.fullmatch(r"[A-Za-z]{2}", segment.strip())):
                continue
            if len(segments) > 2 and re.fullmatch(r"(?:[KW][A-Z]{2,3}|C[A-Z]{3})(?:-(?:TV|LD|CD|DT))?", segment.strip()):
                continue
            match = match_name(segment, name_index, variant=variant, catalog_id=catalog_id)
            if match["reason"] == "ambiguous":
                return {**match, "method": "name_segment"}
            if match["path"]:
                evidence.append((match["path"], "name_segment", key))
            station_paths = (station_name_index or {}).get(key, ())
            station_path = select_variant(station_paths, variant, catalog_id)
            if station_paths and station_path is None:
                return {"path": None, "reason": "ambiguous", "method": "station_name", **candidate_details(station_paths)}
            if station_path:
                evidence.append((station_path, "station_name", key))
    elif station_name_index:
        key = normalize_name(name, prefix, mode)
        station_paths = station_name_index.get(key, ())
        station_path = select_variant(station_paths, variant, catalog_id)
        if station_paths and station_path is None:
            return {"path": None, "reason": "ambiguous", "method": "station_name", **candidate_details(station_paths)}
        if station_path:
            evidence.append((station_path, "station_name", key))

    # A parenthesized acronym is explicit alternative name evidence, not a
    # license to substitute a loosely related network. Ignore quality tags and
    # call signs, which are handled separately.
    for alias in re.findall(r"\(([A-Z0-9]{3,10})\)", name):
        if re.fullmatch(_STATION_TOKEN, alias):
            continue
        match = match_name(alias, name_index, variant=variant, catalog_id=catalog_id)
        if match["reason"] == "ambiguous":
            return {**match, "method": "name_alias"}
        if match["path"]:
            evidence.append((match["path"], "name_alias", normalize_name(alias)))

    paths = {path for path, _, _ in evidence}
    station_matches = {path for path, method, _ in evidence if method in {"callsign", "guide_callsign", "station_name"}}
    if len(paths) > 1 and len(station_matches) == 1:
        # A station-specific file may refine an exact generic city logo, but
        # only when its filename begins with every competing exact name.
        station_path = next(iter(station_matches))
        station_key = normalize_name(PurePosixPath(station_path).stem)
        if all(path == station_path or (key and station_key.startswith(key))
               for path, _, key in evidence):
            paths = {station_path}
    if len(paths) > 1:
        return {"path": None, "reason": "conflicting_matches", "method": "combined", **candidate_details(paths)}
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
