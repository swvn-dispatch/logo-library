from contextlib import contextmanager
import unittest

from src.automatic_run import run_automatic


class Catalog:
    id = "tv_logos"

    def __init__(self):
        self.reads = 0

    def options(self, data_dir):
        self.reads += 1
        return ["countries/united-states/abc-us.png", "countries/united-states/news-us.png"]

    @contextmanager
    def resolve(self, data_dir, path):
        yield path


class AutomaticRunTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.settings = {"automatic_groups": [{"group": "1", "strategy": "exact", "catalog": "tv_logos",
                                               "scope": "countries/united-states"}]}
        self.calls = []

    def assign(self, *args):
        self.calls.append(args)

    def run_match(self, channels, assign=None):
        return run_automatic("/data", self.settings, channels, [1], [self.catalog], assign or self.assign)

    def test_applies_matches_once_and_caches_index(self):
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"},
                                 {"id": 2, "group_id": 1, "name": "News"}])
        self.assertEqual((result["applied"], result["skipped"], result["failed"]), (2, 0, 0))
        self.assertEqual(self.catalog.reads, 1)
        self.assertEqual(self.calls[0][4], "tv_logos:countries/united-states/abc-us.png")

    def test_skips_manual_existing_missing_duplicate_and_no_match(self):
        self.settings["mappings"] = [{"channel": "1", "logo": ""}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"},
                                 {"id": 2, "group_id": 1, "name": "ABC", "logo_id": 8},
                                 {"id": 3, "group_id": None, "name": "ABC"},
                                 {"id": 4, "group_id": 1, "name": "Unknown"},
                                 {"id": 5, "group_id": 1, "name": "ABC"},
                                 {"id": 5, "group_id": 1, "name": "ABC"}])
        self.assertEqual([entry["reason"] for entry in result["channels"]],
                         ["manual_mapping", "existing_logo", "missing_group", "no_match",
                          "duplicate_channel", "duplicate_channel"])
        self.assertEqual(self.calls, [])

    def test_guard_skip_and_failure_are_isolated(self):
        def assign(channel, *args):
            if channel == "1":
                return "settings_changed"
            if channel == "2":
                raise ValueError("write failed")

        result = self.run_match([{"id": i, "group_id": 1, "name": "ABC"} for i in (1, 2, 3)], assign)
        self.assertEqual((result["applied"], result["skipped"], result["failed"]), (1, 1, 1))
        self.assertEqual(result["channels"][0]["reason"], "settings_changed")
        self.assertEqual(result["channels"][1]["reason"], "write failed")

    def test_bad_configuration_and_manual_settings_fail_closed(self):
        self.settings["automatic_groups"] *= 2
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertEqual(len(result["configuration_errors"]), 2)
        self.assertEqual(result["channels"][0]["reason"], "group_not_enabled")
        self.settings["mappings"] = None
        with self.assertRaises(ValueError):
            self.run_match([])

    def test_replace_policy_and_fuzzy_report(self):
        self.settings["automatic_groups"][0].update(strategy="fuzzy", threshold=99, replace=True)
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABCD", "logo_id": 2}])
        self.assertEqual(result["channels"][0]["reason"], "below_threshold")
        self.assertLess(result["channels"][0]["score"], 99)
