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
        self.assertEqual(self.calls[0][5], "tv_logos:countries/united-states/abc-us.png")

    def test_skips_manual_existing_duplicate_and_no_match(self):
        self.settings["mappings"] = [{"channel": "1", "logo": ""}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"},
                                 {"id": 2, "group_id": 1, "name": "ABC", "logo_id": 8},
                                 {"id": 3, "group_id": None, "name": "ABC"},
                                 {"id": 4, "group_id": 1, "name": "Unknown"},
                                 {"id": 5, "group_id": 1, "name": "ABC"},
                                 {"id": 5, "group_id": 1, "name": "ABC"}])
        self.assertEqual([entry["reason"] for entry in result["channels"]],
                         ["manual_mapping", "existing_logo", "no_match",
                          "duplicate_channel", "duplicate_channel"])
        self.assertEqual(result["skipped"], 5)
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
        self.assertEqual(result["channels"], [])
        self.assertEqual(result["skipped"], 0)
        self.settings["mappings"] = None
        with self.assertRaises(ValueError):
            self.run_match([])

    def test_disabled_unconfigured_and_missing_groups_are_omitted(self):
        self.settings["automatic_groups"].append({"group": "2", "strategy": "disabled"})
        self.settings["mappings"] = [{"channel": "3"}]
        channels = [{"id": 1, "group_id": 1, "name": "ABC"},
                    {"id": 2, "group_id": 2, "name": "ABC"},
                    {"id": 3, "group_id": 3, "name": "ABC"},
                    {"id": 4, "group_id": None, "name": "ABC"},
                    {"id": 5, "group_id": 99, "name": "ABC"}]
        result = run_automatic("/data", self.settings, channels, [1, 2, 3], [self.catalog], self.assign)
        self.assertEqual((result["applied"], result["skipped"], result["failed"]), (1, 0, 0))
        self.assertEqual([row["channel"] for row in result["channels"]], ["1"])

    def test_replace_policy_and_fuzzy_report(self):
        self.settings["automatic_groups"][0].update(strategy="fuzzy", replace=True)
        self.settings["automatic_threshold"] = 99
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABCD", "logo_id": 2}])
        self.assertEqual(result["channels"][0]["reason"], "below_threshold")
        self.assertLess(result["channels"][0]["score"], 99)

    def test_missing_scope_is_a_configuration_error(self):
        self.settings["automatic_groups"][0]["scope"] = "united-states"
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertIn("scope contains no indexed logos", result["configuration_errors"][0])
        self.assertEqual(result["channels"], [])
        self.assertEqual(self.calls, [])

    def test_group_regex_prefix_is_used_end_to_end(self):
        self.settings["automatic_prefix_rules"] = [{"group": "1", "mode": "regex", "prefix": r"^(?:US|CA)\s*\|\s*"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "CA | ABC"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(self.calls[0][4]["prefix_mode"], "regex")

    def test_generic_fallback_is_guarded_and_reported(self):
        self.settings["automatic_generic_fallback"] = True
        result = self.run_match([{"id": 1, "group_id": 1, "name": "US | ABC Chicago | WLS"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(result["channels"][0]["method"], "network_fallback")
        self.assertTrue(self.calls[0][4]["generic_fallback"])

    def test_station_name_index_is_used_by_run(self):
        self.catalog.options = lambda data_dir: ["countries/canada/cbc-toronto-ca.png",
                                                "countries/canada/local/cbc-toronto-cblt-ca.png"]
        self.settings["automatic_groups"][0]["scope"] = "countries/canada"
        result = self.run_match([{"id": 1, "group_id": 1, "name": "CBC Toronto"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(result["channels"][0]["method"], "station_name")
        self.assertEqual(self.calls[0][5], "tv_logos:countries/canada/local/cbc-toronto-cblt-ca.png")
