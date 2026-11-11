"""Download and safely publish immutable tv-logos catalog snapshots."""

import fcntl
import json
import logging
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import re
import urllib.request
import uuid
import zipfile
from contextlib import contextmanager

ARCHIVE_URL = "https://github.com/tv-logo/tv-logos/archive/refs/heads/main.zip"
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_EXTRACTED_BYTES = 1024 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_ENTRIES = 100_000
CHUNK_SIZE = 1024 * 1024
_SNAPSHOT_NAME = re.compile(r"snapshot-[0-9a-f]{32}\Z")
logger = logging.getLogger(__name__)


class CatalogError(Exception):
    """A catalog could not be downloaded, validated, or opened."""


@contextmanager
def catalog_lock(data_dir, exclusive):
    """Coordinate updates and readers across local Dispatcharr processes."""
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "catalog.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def current_catalog(data_dir):
    """Return the active snapshot path, or None if no catalog exists."""
    root = Path(data_dir)
    try:
        name = json.loads((root / "catalog.json").read_text(encoding="utf-8"))["snapshot"]
    except FileNotFoundError:
        return None
    except (ValueError, KeyError, TypeError) as exc:
        raise CatalogError("Catalog metadata is invalid") from exc
    if not isinstance(name, str) or not _SNAPSHOT_NAME.fullmatch(name):
        raise CatalogError("Catalog snapshot name is invalid")
    path = root / name
    if path.is_symlink() or not path.is_dir():
        raise CatalogError("Catalog snapshot is missing")
    return path


def logo_paths(snapshot):
    """List UTF-8 repository paths without exposing filesystem surrogates."""
    if snapshot is None:
        return []
    root = os.fsencode(snapshot)
    result = []
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
        for name in files:
            path = os.path.join(base, name)
            if not name.lower().endswith(b".png") or not os.path.isfile(path) or os.path.islink(path):
                continue
            try:
                result.append(os.path.relpath(path, root).decode("utf-8"))
            except UnicodeDecodeError:
                logger.warning("Skipping catalog logo with a non-UTF-8 filename: %r", path)
    return sorted(result, key=str.casefold)


def resolve_logo(snapshot, relative):
    """Resolve a selected image without allowing traversal or symlinks."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise CatalogError("Invalid logo path")
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise CatalogError("Invalid logo path")
    if Path(relative).suffix.lower() != ".png":
        raise CatalogError("Logo must be a PNG")
    root = Path(snapshot)
    candidate = root
    for part in parts:
        try:
            filesystem_part = os.fsdecode(part.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise CatalogError("Invalid logo path encoding") from exc
        candidate = candidate / filesystem_part
        if candidate.is_symlink():
            raise CatalogError("Logo path contains a symlink")
    if not candidate.is_file():
        raise CatalogError(f"Logo not found: {relative}")
    return candidate


def _download(destination, opener):
    request = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "Dispatcharr-Logo-Library"})
    total = 0
    with opener(request, timeout=60) as response, open(destination, "wb") as output:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARCHIVE_BYTES:
                raise CatalogError("Catalog archive exceeds the size limit")
            output.write(chunk)


def _extract(archive, destination):
    count = 0
    total = 0
    root_name = None
    seen = set()
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) > MAX_ENTRIES:
            raise CatalogError("Catalog archive has too many entries")
        for entry in entries:
            name = entry.filename
            parts = name.rstrip("/").split("/")
            if not name or "\\" in name or any(p in ("", ".", "..") for p in parts):
                raise CatalogError("Catalog archive contains an unsafe path")
            if root_name is None:
                root_name = parts[0]
            if parts[0] != root_name:
                raise CatalogError("Catalog archive has multiple roots")
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise CatalogError("Catalog archive contains a symlink")
            if entry.is_dir() or len(parts) < 2 or PurePosixPath(name).suffix.lower() != ".png":
                continue
            relative = "/".join(parts[1:])
            if relative in seen:
                raise CatalogError("Catalog archive contains duplicate paths")
            seen.add(relative)
            total += entry.file_size
            if entry.file_size > MAX_IMAGE_BYTES or total > MAX_EXTRACTED_BYTES:
                raise CatalogError("Catalog images exceed the size limit")
            target = destination.joinpath(*(os.fsdecode(part.encode("utf-8")) for part in parts[1:]))
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as image, target.open("xb") as output:
                shutil.copyfileobj(image, output, CHUNK_SIZE)
            count += 1
    if not count:
        raise CatalogError("Catalog archive contains no PNG images")
    return count


def _cleanup_snapshots(root, keep):
    """Remove only owned snapshots, while holding the exclusive catalog lock."""
    for path in root.iterdir():
        if path.name in keep or not _SNAPSHOT_NAME.fullmatch(path.name):
            continue
        if path.is_symlink() or not path.is_dir():
            continue
        try:
            shutil.rmtree(path)
        except OSError:
            logger.warning("Could not remove old catalog snapshot %s", path, exc_info=True)


def update_catalog(data_dir, opener=urllib.request.urlopen, only_if_missing=False):
    """Publish a complete snapshot while retaining the prior one on failure.

    Readers must hold the shared catalog lock for the whole snapshot read.
    The active and immediately preceding snapshots are retained.
    """
    root = Path(data_dir)
    with catalog_lock(root, exclusive=True):
        previous = current_catalog(root)
        if only_if_missing and previous is not None:
            return None
        with tempfile.TemporaryDirectory(prefix="catalog-update-", dir=root) as temp:
            temp_path = Path(temp)
            archive = temp_path / "catalog.zip"
            snapshot = temp_path / "snapshot"
            snapshot.mkdir()
            try:
                _download(archive, opener)
                count = _extract(archive, snapshot)
            except (OSError, zipfile.BadZipFile, EOFError) as exc:
                raise CatalogError(f"Catalog update failed: {exc}") from exc
            name = "snapshot-" + uuid.uuid4().hex
            os.replace(snapshot, root / name)
            marker = temp_path / "catalog.json"
            marker.write_text(json.dumps({"snapshot": name}), encoding="utf-8")
            os.replace(marker, root / "catalog.json")
            _cleanup_snapshots(root, {name, previous.name if previous else name})
            return count
