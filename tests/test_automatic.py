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
