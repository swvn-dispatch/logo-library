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
