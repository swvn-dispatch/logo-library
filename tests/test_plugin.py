import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import Plugin
from src.fields import make_fields


class PluginTests(unittest.TestCase):
    def test_manifest_contract(self):
        manifest = json.loads((Path(__file__).parents[1] / "src" / "plugin.json").read_text())
        self.assertEqual(manifest["manifest_version"], 2)
        self.assertEqual({action["id"] for action in manifest["actions"]}, {"update_catalog", "apply_changes"})
        self.assertTrue(all(action["async"] for action in manifest["actions"]))

    def test_missing_selections_remain_options(self):
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, {"mappings": [{"channel": "123", "logo": "old/a.png"}]}, [])
            by_id = {field["id"]: field for field in fields}
            self.assertIn("Reload plugin", by_id["instructions"]["description"])
            columns = by_id["mappings"]["columns"]
            self.assertEqual(columns[0]["options"][0]["value"], "123")
            self.assertEqual(columns[1]["options"][0]["value"], "old/a.png")

    def test_settings_sections_and_top_notice(self):
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, {}, [])
        self.assertEqual([field["id"] for field in fields], [
            "instructions", "manual_assignment", "manual_instructions", "mappings",
            "automatic_assignment", "automatic_coming_soon",
        ])
        by_id = {field["id"]: field for field in fields}
        self.assertNotIn("section", by_id["instructions"])
        self.assertEqual(by_id["manual_assignment"]["type"], "section")
        self.assertEqual(by_id["manual_instructions"]["section"], "manual_assignment")
        self.assertEqual(by_id["mappings"]["section"], "manual_assignment")
        self.assertEqual(by_id["automatic_assignment"]["type"], "section")
        self.assertEqual(by_id["automatic_coming_soon"]["section"], "automatic_assignment")
        self.assertIn("coming soon", by_id["automatic_coming_soon"]["description"])

    def test_leader_initial_download_is_queued_only_when_missing(self):
        plugin = Plugin()
        calls = []
        with tempfile.TemporaryDirectory() as root:
            with patch("src.current_catalog", return_value=None):
                plugin.on_leader_acquired({"data_dir": root, "dispatch_task": lambda *args: calls.append(args)})
            with patch("src.current_catalog", return_value=Path(root)):
                plugin.on_leader_acquired({"data_dir": root, "dispatch_task": lambda *args: calls.append(args)})
        self.assertEqual(calls, [("update_catalog", {"initial": True})])

    def test_action_reports_partial_result(self):
        with patch("src.apply_mappings", return_value={"applied": 1, "skipped": 1, "errors": [
            {"row": 2, "channel": "44", "message": "missing"}
        ]}):
            result = Plugin().run("apply_changes", {}, {"data_dir": "/x", "settings": {"mappings": []}})
        self.assertEqual(result["status"], "partial")
        self.assertIn("channel 44", result["message"])

    def test_unknown_action(self):
        self.assertEqual(Plugin().run("unknown", {}, {})["status"], "error")


if __name__ == "__main__":
    unittest.main()
