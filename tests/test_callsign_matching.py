import unittest

from src.callsign_matching import build_callsign_index, match_callsign


class CallSignTests(unittest.TestCase):
    def test_local_station_and_suffix(self):
        path = "countries/united-states/us-local/abc-7-wabc-us.png"
        index = build_callsign_index([path], "tv_logos")
        self.assertEqual(match_callsign("ABC 7 (WABC-TV)", index)["path"], path)
        self.assertEqual(match_callsign("ABC 7 (wabc)", index)["reason"], "no_callsign")

    def test_callsigns_work_in_different_name_formats(self):
        path = "countries/united-states/us-local/abc-7-wabc-us.png"
        index = build_callsign_index([path], "tv_logos")
        for name in ("US | ABC New York | WABC", "WABC-TV New York", "ABC 7 (WABC)", "New York: WABC"):
            with self.subTest(name=name):
                self.assertEqual(match_callsign(name, index)["path"], path)

    def test_only_complete_tokens_are_matched(self):
        path = "countries/united-states/us-local/abc-7-wabco-us.png"
        index = build_callsign_index([path], "tv_logos")
        self.assertEqual(match_callsign("WABC", index)["reason"], "no_match")
        self.assertEqual(match_callsign("XWABCY", index)["reason"], "no_callsign")

    def test_ambiguous_variants_and_multiple_callsigns_are_skipped(self):
        paths = ["countries/united-states/us-local/abc-13-ktnv-us.png",
                 "countries/united-states/us-local/abc-13-ktnv-hz-us.png"]
        index = build_callsign_index(paths, "tv_logos")
        self.assertEqual(match_callsign("KTNV", index)["reason"], "ambiguous")
        self.assertEqual(match_callsign("KTNV KABC", index)["reason"], "ambiguous_callsign")

    def test_generic_paths_other_catalogs_and_scope_are_excluded(self):
        paths = ["countries/canada/city-tv-ca.png", "countries/united-states/wabc-us.png",
                 "countries/united-states/us-local/abc-7-wabc-us.png",
                 "countries/united-states/us-local/cw/cw-7-wabc-us.png"]
        index = build_callsign_index(paths, "tv_logos", "countries/united-states/us-local/cw")
        self.assertEqual(match_callsign("WABC", index)["path"], paths[3])
        self.assertEqual(match_callsign("CITY", build_callsign_index(paths, "tv_logos"))["reason"], "no_match")
        self.assertEqual(match_callsign("WABC", build_callsign_index(paths, "other"))["reason"], "no_match")
        self.assertEqual(match_callsign("WABC", build_callsign_index(paths, "tv_logos", "countries/united-states/us"))["reason"], "no_match")

    def test_invalid_scope_rejected_even_for_other_catalog(self):
        with self.assertRaises(ValueError):
            build_callsign_index([], "other", "../us")

    def test_local_layout_and_callsign_position_not_tied_to_country(self):
        paths = ["countries/example/local/network-city-wabc-xx.png",
                 "countries/example/region-local/nested/network-city-wabc-hz-xx.png",
                 "countries/example/network-city-wabc-xx.png",
                 "countries/example/local/wabc-network-xx.png"]
        index = build_callsign_index(paths, "tv_logos")
        self.assertEqual(set(index["WABC"]), set(paths[:2]))


if __name__ == "__main__":
    unittest.main()
