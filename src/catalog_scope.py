"""Validate and iterate paths inside a catalog-relative directory."""

from pathlib import PurePosixPath


def scoped_paths(paths, scope=""):
    scope_path = PurePosixPath(scope)
    if scope_path.is_absolute() or ".." in scope_path.parts or "\\" in scope or "\x00" in scope:
        raise ValueError("Invalid catalog path scope")
    scope_parts = scope_path.parts
    for value in paths:
        if not isinstance(value, str) or "\\" in value or "\x00" in value:
            continue
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.parts[:len(scope_parts)] != scope_parts:
            continue
        if len(path.parts) > len(scope_parts):
            yield value, path
