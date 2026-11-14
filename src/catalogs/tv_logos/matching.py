"""Matching conventions for tv-logo/tv-logos catalog paths."""

from pathlib import PurePosixPath
import re

from ..matching import GenericMatching

_VARIANTS = {"hd", "hz", "horizontal"}
_CALLSIGN = re.compile(r"(?:[kw][a-z]{2,3}|c[a-z]{3})")


def _country_suffix(parts, path):
    """Recognize the catalog's final two- or three-letter region code."""
    return (len(path.parts) >= 3 and path.parts[0] == "countries" and len(parts) > 1
            and parts[-1].casefold() not in _VARIANTS
            and re.fullmatch(r"[a-z]{2,3}", parts[-1].casefold()) is not None)


def _station_parts(path):
    if len(path.parts) < 4 or path.parts[0] != "countries":
        return None
    if not any(part == "local" or part.endswith("-local") for part in path.parts[2:-1]):
        return None
    parts = path.stem.lower().split("-")
    if not _country_suffix(parts, path):
        return None
    parts.pop()
    while len(parts) > 1 and parts[-1] in _VARIANTS:
        parts.pop()
    return parts if len(parts) > 1 and _CALLSIGN.fullmatch(parts[-1]) else None


class TvLogosMatching(GenericMatching):
    def filename_name(self, path):
        parts = path.stem.split("-")
        if _country_suffix(parts, path):
            parts.pop()
        while len(parts) > 1 and parts[-1].casefold() in _VARIANTS:
            parts.pop()
        return "-".join(parts)

    def callsigns(self, path):
        parts = _station_parts(path)
        return (parts[-1].upper(),) if parts else ()

    def station_name(self, path):
        parts = _station_parts(path)
        if not parts or path.stem.lower().split("-")[-2] in _VARIANTS:
            return None
        return "-".join(parts[:-1])

    def is_generic_network(self, path):
        return (len(path.parts) >= 3 and path.parts[0] == "countries"
                and path.parts[2:-1] in ((), ("hd",)))

    def variant_family(self, path):
        path = PurePosixPath(path)
        parts = path.stem.casefold().split("-")
        country = parts.pop() if _country_suffix(parts, path) else ""
        variants = set()
        while len(parts) > 1 and parts[-1] in _VARIANTS:
            variants.add(parts.pop())
        parents = list(path.parts[:-1])
        if parents and parents[-1] == "hd":
            variants.add("hd")
            parents.pop()
        return (tuple(parents), tuple(parts), country), variants
