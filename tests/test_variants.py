import unittest

from src.callsign_matching import build_callsign_index, match_callsign
from src.fuzzy_matching import match_fuzzy
from src.name_matching import build_name_index, match_name
from src.variants import select_variant


class VariantTests(unittest.TestCase):
    def test_hd_preference_and_conservative_fallback(self):
        base = "countries/united-kingdom/bbc-one-uk.png"
        hd = "countries/united-kingdom/hd/bbc-one-hd-uk.png"
        horizontal = "countries/united-kingdom/bbc-one-hz-uk.png"
        second_hd = "countries/united-kingdom/bbc-one-hd-uk.png"
        unrelated = "countries/united-kingdom/bbc-two-hd-uk.png"
        self.assertEqual(select_variant([base, hd, horizontal], "hd", "tv_logos"), hd)
        self.assertEqual(select_variant([base, horizontal], "hd", "tv_logos"), base)
        self.assertIsNone(select_variant([base, hd, second_hd], "hd", "tv_logos"))
        self.assertIsNone(select_variant([base, hd, unrelated], "hd", "tv_logos"))
        self.assertIsNone(select_variant([base, hd], "hd", "other"))

    def test_standard_preference_requires_one_recognized_family(self):
        base = "countries/united-kingdom/bbc-one-uk.png"
        hd = "countries/united-kingdom/hd/bbc-one-hd-uk.png"
        horizontal = "countries/united-kingdom/bbc-one-hz-uk.png"
        self.assertIsNone(select_variant([base, hd, horizontal]))
        self.assertEqual(select_variant([base, hd, horizontal], "standard", "tv_logos"), base)
        self.assertIsNone(select_variant([base, hd, "countries/united-kingdom/bbc-one-white-uk.png"], "standard", "tv_logos"))
        self.assertIsNone(select_variant([hd, horizontal], "standard", "tv_logos"))
        self.assertIsNone(select_variant([base, hd], "standard", "other"))

    def test_name_and_fuzzy_use_variant_preference_and_regex_prefix(self):
        paths = ["countries/united-kingdom/bbc-one-uk.png", "countries/united-kingdom/hd/bbc-one-hd-uk.png"]
        index = build_name_index(paths, "tv_logos")
        prefix = r"^(?:UK|GB)\s*[-|:]\s*"
        self.assertEqual(match_name("GB: BBC One", index, prefix, "regex")["reason"], "ambiguous")
        self.assertEqual(match_name("GB: BBC One", index, prefix, "regex", "standard", "tv_logos")["path"], paths[0])
        self.assertEqual(match_fuzzy("UK | BBC One", index, 80, prefix, "regex", "standard", "tv_logos")["path"], paths[0])
        self.assertEqual(match_name("GB: BBC One", index, prefix, "regex", "hd", "tv_logos")["path"], paths[1])
        self.assertEqual(match_fuzzy("UK | BBC One", index, 80, prefix, "regex", "hd", "tv_logos")["path"], paths[1])
        self.assertEqual(match_name("OTHER UK | BBC One", index, prefix, "regex", "standard", "tv_logos")["reason"], "no_match")

    def test_callsign_standard_preference_does_not_guess_between_stations(self):
        base = "countries/united-states/us-local/abc-7-wabc-us.png"
        variant = "countries/united-states/us-local/abc-7-wabc-hz-us.png"
        other = "countries/united-states/us-local/abc-8-wabc-hz-us.png"
        index = build_callsign_index([base, variant], "tv_logos")
        self.assertEqual(match_callsign("WABC", index, "standard", "tv_logos")["path"], base)
        index = build_callsign_index([base, variant, other], "tv_logos")
        self.assertEqual(match_callsign("WABC", index, "standard", "tv_logos")["reason"], "ambiguous")
