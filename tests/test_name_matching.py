import unittest

from src.name_matching import build_name_index, match_name, normalize_name


class NameMatchingTests(unittest.TestCase):
    def test_first_matching_cleanup_rule_wins(self):
        from src.name_cleanup import clean_channel_name
        rows = [{"mode": "starts_with", "text": "CA"}, {"mode": "regex", "text": r"^CA\s+NEWS"}]
        self.assertEqual(clean_channel_name("ca News", rows), " News")
        self.assertEqual(clean_channel_name("US News", rows), "US News")
        self.assertEqual(clean_channel_name("News FHD", [{"mode": "ends_with", "text": "FHD"}]), "News ")
        self.assertEqual(clean_channel_name("News HD Plus HD", [{"mode": "regex", "text": "HD"}]), "News  Plus HD")

    def test_legacy_regex_migration_remains_anchored(self):
        from src.name_cleanup import cleanup_rows, clean_channel_name
        rules = cleanup_rows({"automatic_prefix": r"(?i)CA\s*\|\s*", "automatic_prefix_mode": "regex"})
        self.assertEqual(clean_channel_name("CA | News", rules), "News")
        self.assertEqual(clean_channel_name("Other CA | News", rules), "Other CA | News")
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

    def test_descriptive_suffixes_are_conservative(self):
        paths = ["countries/canada/ctv-comedy-channel-ca.png", "countries/canada/ctv-ca.png",
                 "countries/canada/ctv-news-ca.png", "countries/canada/ctv-news-network-ca.png"]
        index = build_name_index(paths, "tv_logos")
        self.assertEqual(match_name("CTV Comedy", index)["path"], paths[0])
        self.assertEqual(match_name("CTV Drama", index)["reason"], "no_match")
        self.assertEqual(match_name("CTV News", index)["path"], paths[2])
        self.assertEqual(match_name("CTV News Channel", index)["path"], paths[2])
        self.assertEqual(match_name("CTV 2", index)["reason"], "no_match")

    def test_reviewed_brand_aliases_are_country_and_catalog_scoped(self):
        paths = ["countries/united-kingdom/4-more-uk.png", "countries/united-states/c-span-1-us.png",
                 "countries/united-states/c-span-2-us.png", "countries/united-states/e-entertainment-us.png"]
        uk = build_name_index(paths, "tv_logos", "countries/united-kingdom")
        us = build_name_index(paths, "tv_logos", "countries/united-states")
        other = build_name_index(paths, "other")
        self.assertEqual(match_name("More4", uk)["path"], paths[0])
        self.assertEqual(match_name("C-Span", us)["path"], paths[1])
        self.assertEqual(match_name("C-Span 2", us)["path"], paths[2])
        self.assertEqual(match_name("E!", us)["path"], paths[3])
        self.assertEqual(match_name("More4", us)["reason"], "no_match")
        self.assertEqual(match_name("More4", other)["reason"], "no_match")

    def test_suffix_alias_does_not_override_exact_name_or_resolve_collisions(self):
        exact = "countries/united-states/news-us.png"
        aliases = ["countries/united-states/news-channel-us.png", "countries/united-states/news-network-us.png"]
        self.assertEqual(match_name("News", build_name_index([exact, *aliases], "tv_logos"))["path"], exact)
        self.assertEqual(match_name("News", build_name_index(aliases, "tv_logos"))["reason"], "ambiguous")

    def test_unverified_renames_and_plus_variants_remain_distinct(self):
        paths = ["countries/united-states/nasa-tv-us.png", "countries/united-states/network-2-us.png"]
        index = build_name_index(paths, "tv_logos")
        self.assertEqual(match_name("NASA+", index)["reason"], "no_match")
        self.assertEqual(match_name("Network", index)["reason"], "no_match")

    def test_invalid_paths_and_scopes(self):
        for scope in ("../us", "/us", "us\\other"):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                build_name_index([], "tv_logos", scope)
        index = build_name_index(["../abc.png", "/abc.png", "us\\abc.png", "abc.png"], "other")
        self.assertEqual(match_name("abc", index)["path"], "abc.png")


if __name__ == "__main__":
    unittest.main()
