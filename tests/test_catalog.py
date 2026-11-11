import io
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from src.catalog import CatalogError, current_catalog, logo_paths, resolve_logo, update_catalog


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
            self.assertEqual(resolve_logo(snapshot, "countries/nordic/a.png").read_bytes(), b"image")
            self.assertIsNone(update_catalog(root, opener(b"invalid"), only_if_missing=True))

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


if __name__ == "__main__":
    unittest.main()
