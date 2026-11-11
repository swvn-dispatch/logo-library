import unittest

from src.fuzzy_matching import match_fuzzy
from src.name_matching import build_name_index


class FuzzyMatchingTests(unittest.TestCase):
    def index(self, names):
        return build_name_index([f"countries/united-states/{name}-us.png" for name in names], "tv_logos")

    def test_unique_highest_wins_even_if_second_is_close(self):
        index = self.index(["animal-planet", "animal-planets"])
        result = match_fuzzy("US: Animal Planet", index, 80, "US:")
        self.assertEqual(result["path"], "countries/united-states/animal-planet-us.png")
        self.assertEqual(result["score"], 100)

    def test_threshold_is_strict_and_score_is_reported(self):
        index = self.index(["animal-planet"])
        self.assertEqual(match_fuzzy("Animal Planet", index, 100)["reason"], "below_threshold")
        result = match_fuzzy("Animal Planets", index, 99)
        self.assertEqual(result["reason"], "below_threshold")
        self.assertLess(result["score"], 99)

    def test_ties_and_duplicate_variants_are_ambiguous(self):
        index = self.index(["abc-news", "abc-news-hz"])
        self.assertEqual(match_fuzzy("ABC News", index, 80)["reason"], "ambiguous")
        self.assertEqual(match_fuzzy("abc", {"abd": ("a",), "abe": ("b",)}, 0)["reason"], "ambiguous")

    def test_numbers_and_plus_variants_are_never_interchanged(self):
        index = self.index(["bbc-11", "5-star-plus", "channel-2"])
        for name in ("BBC 1", "5 Star", "Channel 12"):
            with self.subTest(name=name):
                self.assertEqual(match_fuzzy(name, index, 0)["reason"], "no_match")

    def test_abbreviations_and_near_identical_networks_need_threshold(self):
        index = self.index(["national-geographic", "newsmax"])
        self.assertEqual(match_fuzzy("Nat Geo", index, 90)["reason"], "below_threshold")
        self.assertEqual(match_fuzzy("Newsmax 2", index, 0)["reason"], "no_match")
        self.assertEqual(match_fuzzy("Newsmaxx", index, 99)["reason"], "below_threshold")

    def test_country_scope_excludes_other_variants(self):
        paths = ["countries/united-states/abc-news-us.png", "countries/united-kingdom/abc-news-uk.png"]
        index = build_name_index(paths, "tv_logos", "countries/united-states")
        self.assertEqual(match_fuzzy("ABC News", index, 80)["path"], paths[0])

    def test_invalid_threshold_and_missing_name(self):
        for threshold in (True, -1, 101, float("nan"), "80"):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                match_fuzzy("abc", {}, threshold)
        self.assertEqual(match_fuzzy("!!!", {}, 50)["reason"], "no_match")
