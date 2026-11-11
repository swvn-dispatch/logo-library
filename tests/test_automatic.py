import unittest

from src.automatic import compile_groups


class AutomaticGroupTests(unittest.TestCase):
    def test_valid_settings_and_disabled_default(self):
        rows = [{"group": "1", "strategy": "fuzzy", "catalog": "tv", "scope": "countries/us/",
                 "threshold": 90, "replace": True}, {"group": "2"}]
        groups, errors = compile_groups(rows, [1, 2], {"tv"})
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
                       {"threshold": 101}, {"threshold": True}, {"replace": "false"},
                       {"catalog": "missing"}, {"strategy": "unknown"}):
            with self.subTest(change=change):
                groups, errors = compile_groups([{**base, **change}], [1], {"tv"})
                self.assertEqual(groups, {})
                self.assertEqual(len(errors), 1)
