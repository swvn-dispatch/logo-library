import io
import tempfile
import unittest
import zipfile

from src.catalog import update_catalog
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
            self.assertEqual(calls, [("1", "a.png", b"image")])
            self.assertEqual([error["row"] for error in result["errors"]], [2, 3, 4, 5])

    def test_missing_catalog_and_incomplete_row(self):
        with tempfile.TemporaryDirectory() as root:
            result = apply_mappings(root, [{"channel": "1", "logo": "a.png"}, {}], lambda *args: None)
            self.assertEqual(result["applied"], 0)
            self.assertEqual(result["skipped"], 2)
            self.assertIn("not been downloaded", result["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
