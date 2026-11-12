import io
from concurrent.futures import ThreadPoolExecutor
import os
import shutil
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from src.catalogs.tv_logos.catalog import (
    INDEX_NAME, CatalogError, current_catalog, ensure_index, logo_paths, read_index,
    release_initialization, reserve_initialization, resolve_logo, update_catalog as _update_catalog,
)
from src.catalogs.tv_logos import TvLogosCatalog


def update_catalog(*args, **kwargs):
    return _update_catalog(*args, **kwargs, remove_directory=shutil.rmtree)


def archive(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as output:
        for name, content in files:
            output.writestr(name, content)
    return buf.getvalue()


def opener(data):
    return lambda request, timeout: io.BytesIO(data)


class CatalogTests(unittest.TestCase):
    def test_update_and_nested_paths(self):
        data = archive([("tv-logos-main/countries/nordic/a.png", b"image"),
                        ("tv-logos-main/README.md", b"readme")])
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(update_catalog(root, opener(data)), 1)
            snapshot = current_catalog(root)
            self.assertEqual(logo_paths(snapshot), ["countries/nordic/a.png"])
            self.assertEqual(read_index(snapshot), ["countries/nordic/a.png"])
            self.assertEqual(resolve_logo(snapshot, "countries/nordic/a.png").read_bytes(), b"image")
            self.assertIsNone(update_catalog(root, opener(b"invalid"), only_if_missing=True))

    def test_options_never_walk_or_wait_for_catalog_lock(self):
        with tempfile.TemporaryDirectory() as root:
            update_catalog(root, opener(archive([("root/a.png", b"image")])))
            with patch("os.walk", side_effect=AssertionError("startup must not walk")), \
                 patch("src.catalogs.tv_logos.catalog.fcntl.flock", side_effect=AssertionError("startup must not lock")):
                self.assertEqual(TvLogosCatalog().options(root), ["a.png"])
                (current_catalog(root) / INDEX_NAME).unlink()
                self.assertEqual(TvLogosCatalog().options(root), [])

    def test_existing_catalog_is_indexed_once(self):
        with tempfile.TemporaryDirectory() as root:
            update_catalog(root, opener(archive([("root/a.png", b"image")])))
            snapshot = current_catalog(root)
            (snapshot / INDEX_NAME).unlink()
            with patch("src.catalogs.tv_logos.catalog.logo_paths", wraps=logo_paths) as scan:
                self.assertEqual(ensure_index(root), 1)
                self.assertEqual(ensure_index(root), 1)
                scan.assert_called_once_with(snapshot)
            self.assertEqual(read_index(snapshot), ["a.png"])

    def test_initialization_requests_are_debounced_and_token_scoped(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("src.catalogs.tv_logos.catalog.time.time", return_value=1000):
                first = reserve_initialization(root)
                self.assertIsNotNone(first)
                self.assertIsNone(reserve_initialization(root))
            with patch("src.catalogs.tv_logos.catalog.time.time", return_value=1400):
                second = reserve_initialization(root)
                self.assertIsNotNone(second)
                release_initialization(root, first)
                self.assertIsNone(reserve_initialization(root))
                release_initialization(root, second)
                self.assertIsNotNone(reserve_initialization(root))

    def test_concurrent_initialization_requests_only_reserve_once(self):
        with tempfile.TemporaryDirectory() as root:
            with ThreadPoolExecutor(max_workers=8) as pool:
                tokens = list(pool.map(lambda _: reserve_initialization(root), range(16)))
            self.assertEqual(sum(token is not None for token in tokens), 1)

    def test_corrupt_index_is_treated_as_missing(self):
        with tempfile.TemporaryDirectory() as root:
            update_catalog(root, opener(archive([("root/a.png", b"image")])))
            snapshot = current_catalog(root)
            (snapshot / INDEX_NAME).write_text("[]")
            self.assertIsNone(read_index(snapshot))
            self.assertEqual(ensure_index(root), 1)

    def test_utf8_paths_work_with_ascii_filesystem_decoding(self):
        names = ["countries/école.png", "countries/новости.png"]
        data = archive([("root/" + name, b"image") for name in names])

        def ascii_fsdecode(path):
            return path.decode("ascii", "surrogateescape") if isinstance(path, bytes) else os.fspath(path)

        with tempfile.TemporaryDirectory() as root, patch("os.fsdecode", side_effect=ascii_fsdecode):
            update_catalog(root, opener(data))
            snapshot = current_catalog(root)
            self.assertEqual(set(logo_paths(snapshot)), set(names))
            for name in names:
                self.assertEqual(resolve_logo(snapshot, name).read_bytes(), b"image")

    def test_non_utf8_filename_is_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            entries = [(os.fsencode(root), [], [b"invalid-\xff.png"])]
            with patch("os.walk", return_value=entries), patch("os.path.isfile", return_value=True), \
                 self.assertLogs("src.catalogs.tv_logos.catalog", level="WARNING"):
                self.assertEqual(logo_paths(root), [])

    def test_failed_update_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            update_catalog(root, opener(archive([("root/a.png", b"old")])))
            before = current_catalog(root)
            with self.assertRaises(CatalogError):
                update_catalog(root, opener(archive([("root/../escape.png", b"bad")])))
            self.assertEqual(current_catalog(root), before)
            self.assertEqual((before / "a.png").read_bytes(), b"old")

    def test_rejects_missing_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            snapshot = Path(root) / "snapshot"
            snapshot.mkdir()
            (snapshot / "link.png").symlink_to(Path(root) / "other.png")
            for path in ("../other.png", "/other.png", "a\\b.png", "link.png", "missing.png"):
                with self.subTest(path=path), self.assertRaises(CatalogError):
                    resolve_logo(snapshot, path)

    def test_rejects_empty_and_duplicate_archives(self):
        with tempfile.TemporaryDirectory() as root:
            for files in ([('root/readme', b'')], [('root/a.png', b'a'), ('root/a.png', b'b')]):
                with self.subTest(files=files), self.assertRaises(CatalogError):
                    update_catalog(root, opener(archive(files)))
            self.assertIsNone(current_catalog(root))

    def test_rejects_archive_symlink(self):
        buffer = io.BytesIO()
        entry = zipfile.ZipInfo("root/link.png")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(buffer, "w") as output:
            output.writestr(entry, "../../outside.png")
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(CatalogError):
                update_catalog(root, opener(buffer.getvalue()))
            self.assertIsNone(current_catalog(root))

    def test_keeps_current_and_previous_owned_snapshots_only(self):
        with tempfile.TemporaryDirectory() as root:
            paths = []
            removed = []
            def remove_directory(path):
                removed.append(path)
                shutil.rmtree(path)
            for i in range(3):
                _update_catalog(root, opener(archive([("root/a.png", str(i).encode())])), remove_directory=remove_directory)
                paths.append(current_catalog(root))
            self.assertFalse(paths[0].exists())
            self.assertEqual(removed, [paths[0]])
            self.assertTrue(paths[1].exists())
            self.assertEqual((paths[2] / "a.png").read_bytes(), b"2")

    def test_cleanup_ignores_unowned_directories_and_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            unrelated = Path(root) / "snapshot-other"
            unrelated.mkdir()
            symlink = Path(root) / ("snapshot-" + "f" * 32)
            symlink.symlink_to(unrelated, target_is_directory=True)
            update_catalog(root, opener(archive([("root/a.png", b"a")])))
            self.assertTrue(unrelated.exists())
            self.assertTrue(symlink.is_symlink())


if __name__ == "__main__":
    unittest.main()
