import unittest

from src.automatic import compile_groups


class AutomaticGroupTests(unittest.TestCase):
    def test_valid_settings_and_disabled_default(self):
        rows = [{"group": "1", "strategy": "fuzzy", "catalog": "tv", "scope": "countries/us/",
                 "threshold": 90, "replace": True}, {"group": "2"}]
        groups, errors = compile_groups(rows, [1, 2], {"tv"}, {"automatic_threshold": 90})
        self.assertEqual(errors, [])
        self.assertEqual(groups["1"]["scope"], "countries/us")
        self.assertTrue(groups["1"]["replace"])
        self.assertNotIn("2", groups)

    def test_catalog_root_scope_accepts_new_and_legacy_values(self):
        for scope in ("", ".", None):
            with self.subTest(scope=scope):
                groups, errors = compile_groups([{"group": "1", "strategy": "exact", "scope": scope}], [1], {"tv"})
                self.assertEqual(errors, [])
                self.assertEqual(groups["1"]["scope"], "")

    def test_duplicates_and_missing_groups_are_rejected(self):
        row = {"group": "1", "strategy": "exact", "catalog": "tv"}
        groups, errors = compile_groups([row, row, {"group": "9"}], [1], {"tv"})
        self.assertEqual(groups, {})
        self.assertEqual(len(errors), 3)

    def test_invalid_settings_fail_closed(self):
        base = {"group": "1", "strategy": "fuzzy", "catalog": "tv", "threshold": 80}
        for change in ({"scope": "../us"}, {"scope": "/us"}, {"scope": "us\\foo"},
                       {"replace": "false"}, {"strategy": "unknown"}):
            with self.subTest(change=change):
                groups, errors = compile_groups([{**base, **change}], [1], {"tv"})
                self.assertEqual(groups, {})
                self.assertEqual(len(errors), 1)

        for threshold in (101, True):
            groups, errors = compile_groups([base], [1], {"tv"}, {"automatic_threshold": threshold})
            self.assertEqual(groups, {})
            self.assertEqual(len(errors), 1)

    def test_shared_tuning_and_implicit_catalog(self):
        rows = [{"group": "1", "strategy": "fuzzy", "catalog": "old", "threshold": 1},
                {"group": "2", "strategy": "exact", "prefix": "old"}]
        groups, errors = compile_groups(rows, [1, 2], {"tv"},
                                        {"automatic_prefix": "US:", "automatic_threshold": 80})
        self.assertEqual(errors, [])
        self.assertEqual(groups["1"]["catalog"], "tv")
        self.assertEqual(groups["1"]["threshold"], 80)
        self.assertEqual(groups["2"]["prefix"], "US:")
        groups, errors = compile_groups(rows, [1, 2], {"tv", "other"})
        self.assertEqual(groups, {})
        self.assertEqual(len(errors), 2)

    def test_group_prefix_rules_override_default_and_validate(self):
        rows = [{"group": "1", "strategy": "exact"}, {"group": "2", "strategy": "exact"}]
        settings = {"automatic_prefix": "default", "automatic_prefix_rules": [
            {"group": "1", "mode": "regex", "prefix": r"^(US|CA)\s*\|\s*"}]}
        groups, errors = compile_groups(rows, [1, 2], {"tv"}, settings)
        self.assertEqual(errors, [])
        self.assertEqual(groups["1"]["prefix_mode"], "regex")
        self.assertEqual(groups["2"]["prefix"], "default")
        settings["automatic_prefix_rules"].append({"group": "1", "mode": "literal", "prefix": "X"})
        groups, errors = compile_groups(rows, [1, 2], {"tv"}, settings)
        self.assertNotIn("1", groups)
        self.assertIn("2", groups)
        self.assertIn("more than one", errors[0])
        settings["automatic_prefix_rules"] = [{"group": "1", "mode": "regex", "prefix": "["}]
        groups, errors = compile_groups(rows, [1, 2], {"tv"}, settings)
        self.assertNotIn("1", groups)
        self.assertIn("Invalid prefix regex", errors[0])

    def test_legacy_shared_groups_are_not_enabled_implicitly(self):
        settings = {"automatic_default_groups": ["1", "2", "3", "4"],
                    "automatic_default_scope": "countries/canada", "automatic_default_replace": True}
        rows = [{"group": "2", "strategy": "exact", "scope": "countries/us", "replace": False},
                {"group": "3", "strategy": "disabled"},
                {"group": "4", "strategy": "invalid"}]
        groups, errors = compile_groups(rows, [1, 2, 3, 4], {"tv"}, settings)
        self.assertNotIn("1", groups)
        self.assertEqual(groups["2"]["scope"], "countries/us")
        self.assertFalse(groups["2"]["replace"])
        self.assertNotIn("3", groups)
        self.assertNotIn("4", groups)
        self.assertEqual(len(errors), 1)
        self.assertIn("Unknown strategy", errors[0])

    def test_legacy_shared_warning_clears_when_rows_are_added(self):
        settings = {"automatic_default_groups": ["1", "2"]}
        rows = [{"group": "1", "strategy": "exact"}, {"group": "2", "strategy": "disabled"}]
        groups, errors = compile_groups(rows, [1, 2], {"tv"}, settings)
        self.assertEqual(errors, [])
        self.assertEqual(set(groups), {"1"})

    def test_removed_shared_groups_that_no_longer_exist_do_not_block(self):
        groups, errors = compile_groups([], [], {"tv"}, {"automatic_default_groups": ["42"]})
        self.assertEqual(groups, {})
        self.assertEqual(errors, [])

    def test_shared_prefix_regex_and_guide_opt_in(self):
        settings = {"automatic_prefix": r"^US\s*\|\s*",
                    "automatic_prefix_mode": "regex", "automatic_guide_signals": True}
        groups, errors = compile_groups([{"group": "1", "strategy": "exact"}], [1], {"tv"}, settings)
        self.assertEqual(errors, [])
        self.assertTrue(groups["1"]["guide_signals"])
        self.assertEqual(groups["1"]["prefix_mode"], "regex")
