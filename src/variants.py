"""Choose preferred logos only within a verified variant family."""

from pathlib import PurePosixPath
from .catalogs.matching import matching_adapter


def select_variant(paths, preference="strict", catalog_id=None):
    """Return a unique path or None; unknown or unrelated variants remain ties."""
    paths = set(paths)
    if len(paths) == 1:
        return next(iter(paths))
    if preference not in {"standard", "hd"} or not paths:
        return None
    adapter = matching_adapter(catalog_id)
    classified = [(path, adapter.variant_family(PurePosixPath(path))) for path in paths]
    if any(family is None for _, family in classified):
        return None
    classified = [(path, *family) for path, family in classified]
    if len({family for _, family, _ in classified}) != 1:
        return None
    if preference == "hd":
        hd = [(path, len(variants - {"hd"})) for path, _, variants in classified if "hd" in variants]
        if hd:
            fewest = min(extra for _, extra in hd)
            preferred = [path for path, extra in hd if extra == fewest]
            return preferred[0] if len(preferred) == 1 else None
    standards = [path for path, _, variant in classified if not variant]
    return standards[0] if len(standards) == 1 else None
