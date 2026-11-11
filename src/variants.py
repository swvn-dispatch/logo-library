"""Choose an optional standard logo only within a verified variant family."""

from pathlib import PurePosixPath


def _family(path):
    path = PurePosixPath(path)
    parts = path.stem.casefold().split("-")
    country = parts.pop() if parts and parts[-1] in {"us", "uk", "ca", "au", "nz"} else ""
    variant = False
    while len(parts) > 1 and parts[-1] in {"hd", "hz", "horizontal"}:
        variant = True
        parts.pop()
    parents = list(path.parts[:-1])
    if parents and parents[-1] == "hd":
        variant = True
        parents.pop()
    return (tuple(parents), tuple(parts), country), variant


def select_variant(paths, preference="strict", catalog_id=None):
    """Return a unique path or None; unknown or unrelated variants remain ties."""
    paths = set(paths)
    if len(paths) == 1:
        return next(iter(paths))
    if preference != "standard" or catalog_id != "tv_logos" or not paths:
        return None
    classified = [(path, *_family(path)) for path in paths]
    if len({family for _, family, _ in classified}) != 1:
        return None
    standards = [path for path, _, variant in classified if not variant]
    return standards[0] if len(standards) == 1 else None
