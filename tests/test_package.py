import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.package import package


class PackageTests(unittest.TestCase):
    def test_package_has_manifest_and_modules_without_cache(self):
        source = Path(__file__).parents[1] / "src"
        original = (source / "plugin.json").read_text()
        with tempfile.TemporaryDirectory() as root:
            path = package(source, root, "0.1.0-dev-12345678")
            self.assertEqual(path.name, "logo-library-0.1.0-dev-12345678.zip")
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                self.assertIn("logo_library/__init__.py", names)
                self.assertIn("logo_library/catalog.py", names)
                self.assertIn("logo_library/plugin.json", names)
                self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))
                manifest = json.loads(archive.read("logo_library/plugin.json"))
                self.assertEqual(manifest["version"], "0.1.0-dev-12345678")
        self.assertEqual((source / "plugin.json").read_text(), original)

    def test_rejects_unsafe_version(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                package(Path(__file__).parents[1] / "src", root, "../bad")


if __name__ == "__main__":
    unittest.main()
