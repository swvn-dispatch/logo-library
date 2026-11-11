import unittest

from src.filters import compile_filters, matches


class FilterTests(unittest.TestCase):
    def test_include_any_and_exclude_case_insensitively(self):
        rules, errors = compile_filters([
            {"mode": "include_contains", "text": "CANADA"},
            {"mode": "include_starts_with", "text": "countries/us/"},
            {"mode": "exclude_contains", "text": "SPORT"},
        ], "tv_logos")
        self.assertEqual(errors, [])
        selected = rules["tv_logos"]
        self.assertTrue(matches("countries/canada/news.png", selected))
        self.assertTrue(matches("countries/US/news.png", selected))
        self.assertFalse(matches("countries/canada/sport.png", selected))
        self.assertFalse(matches("countries/france/news.png", selected))

    def test_exact_regex_and_exclude_only(self):
        rules, errors = compile_filters([
            {"mode": "include_exact", "text": "CA/ONE.PNG"},
            {"mode": "include_regex", "text": r"^us/.*\.png$"},
            {"mode": "exclude_exact", "text": "US/BAD.PNG"},
            {"catalog": "other", "mode": "exclude_starts_with", "text": "hidden/"},
        ], "tv_logos")
        self.assertEqual(errors, [])
        self.assertTrue(matches("ca/one.png", rules["tv_logos"]))
        self.assertTrue(matches("US/good.png", rules["tv_logos"]))
        self.assertFalse(matches("us/bad.png", rules["tv_logos"]))
        self.assertTrue(matches("visible/a.png", rules["other"]))
        self.assertFalse(matches("hidden/a.png", rules["other"]))

    def test_invalid_patterns_are_ignored(self):
        rows = [{"mode": "include_regex", "text": value} for value in ("[", "(abc", "*")]
        rules, errors = compile_filters(rows, "tv_logos")
        self.assertEqual(rules, {})
        self.assertEqual(len(errors), len(rows))
        self.assertTrue(matches("any.png", []))

    def test_full_python_regex_syntax(self):
        rows = [{"mode": "include_regex", "text": r"^(?=ca/)ca/(ab){2}.*\.png$"}]
        rules, errors = compile_filters(rows, "tv_logos")
        self.assertEqual(errors, [])
        self.assertTrue(matches("CA/abab-news.png", rules["tv_logos"]))
        self.assertFalse(matches("us/abab-news.png", rules["tv_logos"]))

    def test_incomplete_rows_report_errors_and_blank_rows_are_ignored(self):
        rules, errors = compile_filters([{}, {"mode": "include_contains"}, {"text": "canada"}], "tv_logos")
        self.assertEqual(rules, {})
        self.assertEqual(len(errors), 2)

    def test_invalid_catalog_and_invalid_unicode_are_reported(self):
        rules, errors = compile_filters([
            {"catalog": [], "mode": "include_contains", "text": "x"},
            {"mode": "include_contains", "text": "\udcc3"},
        ], None)
        self.assertEqual(rules, {})
        self.assertEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
