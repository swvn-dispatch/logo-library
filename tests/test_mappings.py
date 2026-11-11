import io
import tempfile
import unittest
import zipfile

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from src.catalogs.tv_logos.catalog import update_catalog
from src.mappings import apply_mappings


class MappingTests(unittest.TestCase):
    def test_partial_success_and_duplicate_channels(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("root/a.png", b"image")
        with tempfile.TemporaryDirectory() as root:
            update_catalog(root, lambda request, timeout: io.BytesIO(buffer.getvalue()))
            calls = []
            rows = [
                {"channel": "1", "logo": "a.png"},
                {"channel": "2", "logo": "a.png"},
                {"channel": "2", "logo": "a.png"},
                {"channel": "3", "logo": "missing.png"},
                {"channel": "4", "logo": "a.png"},
            ]

            def assign(channel, relative, image):
                if channel == "4":
                    raise ValueError("Channel no longer exists")
                calls.append((channel, relative, image.read_bytes()))

            result = apply_mappings(root, rows, assign)
            self.assertEqual(result["applied"], 1)
            self.assertEqual(result["skipped"], 4)
            self.assertEqual(calls, [("1", "tv_logos:a.png", b"image")])
            self.assertEqual([error["row"] for error in result["errors"]], [2, 3, 4, 5])

    def test_missing_catalog_and_incomplete_row(self):
        with tempfile.TemporaryDirectory() as root:
            result = apply_mappings(root, [{"channel": "1", "logo": "a.png"}, {}], lambda *args: None)
            self.assertEqual(result["applied"], 0)
            self.assertEqual(result["skipped"], 2)
            self.assertIn("not been downloaded", result["errors"][0]["message"])

    def test_two_catalogs_with_same_path_are_distinct(self):
        class FakeCatalog:
            accepts_legacy_paths = False

            def __init__(self, catalog_id):
                self.id = catalog_id

            @contextmanager
            def resolve(self, data_dir, path):
                yield Path(data_dir) / self.id

        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "first").write_bytes(b"first")
            (Path(root) / "second").write_bytes(b"second")
            catalogs = (FakeCatalog("first"), FakeCatalog("second"))
            rows = [{"channel": "1", "logo": "first:same.png"},
                    {"channel": "2", "logo": "second:same.png"}]
            calls = []
            with patch("src.catalogs.CATALOGS", catalogs):
                result = apply_mappings(root, rows, lambda channel, identity, path: calls.append((identity, path.read_bytes())))
            self.assertEqual(result["applied"], 2)
            self.assertEqual(calls, [("first:same.png", b"first"), ("second:same.png", b"second")])


if __name__ == "__main__":
    unittest.main()
