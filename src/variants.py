"""Choose preferred logos only within a verified variant family."""

from pathlib import PurePosixPath


def _family(path):
    path = PurePosixPath(path)
    parts = path.stem.casefold().split("-")
    country = parts.pop() if parts and parts[-1] in {"us", "uk", "ca", "au", "nz"} else ""
    variants = set()
    while len(parts) > 1 and parts[-1] in {"hd", "hz", "horizontal"}:
        variants.add(parts.pop())
    parents = list(path.parts[:-1])
    if parents and parents[-1] == "hd":
        variants.add("hd")
        parents.pop()
    return (tuple(parents), tuple(parts), country), variants


def select_variant(paths, preference="strict", catalog_id=None):
    """Return a unique path or None; unknown or unrelated variants remain ties."""
    paths = set(paths)
    if len(paths) == 1:
        return next(iter(paths))
    if preference not in {"standard", "hd"} or catalog_id != "tv_logos" or not paths:
        return None
    classified = [(path, *_family(path)) for path in paths]
    if len({family for _, family, _ in classified}) != 1:
        return None
    if preference == "hd":
        hd = [path for path, _, variants in classified if "hd" in variants]
        if hd:
            return hd[0] if len(hd) == 1 else None
    standards = [path for path, _, variant in classified if not variant]
    return standards[0] if len(standards) == 1 else None
