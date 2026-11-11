import unittest

from src.name_matching import build_name_index, match_name, normalize_name


class NameMatchingTests(unittest.TestCase):
    def test_unicode_punctuation_prefix_and_ampersand(self):
        index = build_name_index(["countries/united-states/café-and-news-us.png"], "tv_logos")
        self.assertEqual(match_name("US: Cafe\u0301 & News", index, "us:")["path"],
                         "countries/united-states/café-and-news-us.png")
        self.assertEqual(match_name("Other US: Café & News", index, "us:")["reason"], "no_match")

    def test_numbers_and_plus_are_distinct(self):
        paths = ["countries/united-kingdom/bbc-one-uk.png", "countries/united-kingdom/bbc-1-uk.png",
                 "countries/united-kingdom/bbc-11-uk.png", "countries/united-kingdom/5-star-plus-uk.png",
                 "countries/united-kingdom/5-star-uk.png"]
        index = build_name_index(paths, "tv_logos")
        self.assertEqual(match_name("BBC 1", index)["path"], paths[1])
        self.assertEqual(match_name("BBC 11", index)["path"], paths[2])
        self.assertEqual(match_name("5 Star+", index)["path"], paths[3])
        self.assertNotEqual(normalize_name("5 Star+"), normalize_name("5 Star"))

    def test_variants_are_ambiguous_and_duplicates_are_deduplicated(self):
        paths = ["countries/united-states/abc-news-us.png", "countries/united-states/abc-news-hz-us.png"]
        self.assertEqual(match_name("ABC News", build_name_index(paths, "tv_logos"))["reason"], "ambiguous")
        self.assertEqual(match_name("ABC News", build_name_index(paths[:1] * 2, "tv_logos"))["path"], paths[0])

    def test_scope_respects_directory_boundaries_and_catalog(self):
        paths = ["countries/united-states/abc-us.png", "countries/united-states-extra/abc-us.png",
                 "countries/united-states/hd/abc-hd-us.png"]
        index = build_name_index(paths, "tv_logos", "countries/united-states")
        self.assertEqual(match_name("ABC", index)["reason"], "ambiguous")
        self.assertEqual(match_name("ABC", build_name_index(paths, "other", "countries/united-states"))["reason"], "no_match")
        self.assertEqual(match_name("ABC", build_name_index(paths, "tv_logos", "countries/united-states-extra"))["reason"], "no_match")

    def test_unrecognized_suffix_is_not_dropped(self):
        index = build_name_index(["countries/france/news-fr.png"], "tv_logos")
        self.assertEqual(match_name("News", index)["reason"], "no_match")

    def test_invalid_paths_and_scopes(self):
        for scope in ("../us", "/us", "us\\other"):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                build_name_index([], "tv_logos", scope)
        index = build_name_index(["../abc.png", "/abc.png", "us\\abc.png", "abc.png"], "other")
        self.assertEqual(match_name("abc", index)["path"], "abc.png")


if __name__ == "__main__":
    unittest.main()
