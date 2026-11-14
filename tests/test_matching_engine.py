import unittest

from src.callsign_matching import build_callsign_index, build_station_name_index
from src.matching_engine import build_network_index, match_channel
from src.name_matching import build_name_index


class MatchingEngineTests(unittest.TestCase):
    def setUp(self):
        self.paths = [
            "countries/canada/local/cbc-montreal-cbmt-ca.png",
            "countries/canada/local/cbc-toronto-cblt-ca.png",
            "countries/canada/cbc-toronto-ca.png",
            "countries/canada/global-montreal-ca.png",
            "countries/canada/global-toronto-ca.png",
            "countries/canada/ctv-ca.png",
            "countries/canada/city-tv-ca.png",
            "countries/canada/rds-ca.png",
            "countries/canada/rds-2-ca.png",
            "countries/canada/tva-sports-ca.png",
            "countries/canada/tva-sports-2-ca.png",
            "countries/united-kingdom/bbc-one-uk.png",
            "countries/united-kingdom/e4-uk.png",
            "countries/united-states/a-and-e-us.png",
            "countries/united-states/us-local/abc-7-wabc-us.png",
        ]
        self.config = {"strategy": "exact", "prefix": "", "prefix_mode": "literal", "variant": "strict", "threshold": 90}

    def match(self, name, scope, strategy="exact"):
        name_index = build_name_index(self.paths, "tv_logos", scope)
        call_index = build_callsign_index(self.paths, "tv_logos", scope)
        return match_channel(name, {**self.config, "strategy": strategy}, name_index, call_index, "tv_logos")

    def test_canadian_station_specific_and_city_evidence(self):
        result = self.match("CA | CBC Montreal | CBMT", "countries/canada", "fuzzy")
        self.assertEqual(result["path"], self.paths[0])
        self.assertEqual(result["method"], "callsign")
        self.assertEqual(self.match("CA | CBC Toronto | CBLT", "countries/canada")["path"], self.paths[1])
        self.assertEqual(self.match("CA | Global Montreal | CKMI", "countries/canada", "callsign")["path"], self.paths[3])
        self.assertEqual(self.match("CA | Global Toronto | CIII", "countries/canada")["path"], self.paths[4])

    def test_missing_station_does_not_fall_back_to_generic_network(self):
        for name in ("CA | CTV Toronto | CFTO", "CA | City TV Toronto | CITY"):
            with self.subTest(name=name):
                self.assertIsNone(self.match(name, "countries/canada", "fuzzy")["path"])

    def test_numbered_qc_uk_and_us_names(self):
        cases = [("CA | RDS", "countries/canada", 7), ("CA | RDS 2", "countries/canada", 8),
                 ("CA | TVA Sports 2", "countries/canada", 10), ("UK | BBC One", "countries/united-kingdom", 11),
                 ("UK | E4", "countries/united-kingdom", 12), ("US | A&E", "countries/united-states", 13),
                 ("ABC New York (WABC)", "countries/united-states", 14)]
        for name, scope, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(self.match(name, scope, "callsign")["path"], self.paths[expected])

    def test_delimiters_are_not_tied_to_country_codes(self):
        self.assertEqual(self.match("Regional - Global Montreal - CKMI", "countries/canada")["path"], self.paths[3])
        self.assertEqual(self.match("Any Provider | RDS 2", "countries/canada")["path"], self.paths[8])

    def test_colon_regions_and_two_letter_channel_names(self):
        paths = ["countries/united-states/fx-us.png", "countries/united-states/abc-us.png"]
        names = build_name_index(paths, "tv_logos")
        self.assertEqual(match_channel("US: FX", self.config, names, {}, "tv_logos")["path"], paths[0])
        self.assertEqual(match_channel("US | FX", self.config, names, {}, "tv_logos")["path"], paths[0])
        self.assertEqual(match_channel("Provider: FX", self.config, names, {}, "tv_logos")["path"], paths[0])

    def test_parenthesized_acronym_is_exact_evidence(self):
        paths = ["countries/canada/cp24-ca.png", "countries/canada/cbc-ca.png"]
        names = build_name_index(paths, "tv_logos")
        self.assertEqual(match_channel("CA: Cable Pulse 24 (CP24)", self.config, names, {}, "tv_logos")["path"], paths[0])
        self.assertIsNone(match_channel("CA: CTV News (HD)", self.config, names, {}, "tv_logos")["path"])

    def test_station_name_without_callsign_uses_exact_city_evidence(self):
        scope = "countries/canada"
        names = build_name_index(self.paths, "tv_logos", scope)
        calls = build_callsign_index(self.paths, "tv_logos", scope)
        stations = build_station_name_index(self.paths, "tv_logos", scope)
        result = match_channel("CBC Toronto", self.config, names, calls, "tv_logos", station_name_index=stations)
        self.assertEqual(result["path"], self.paths[1])
        self.assertEqual(result["method"], "station_name")
        result = match_channel("CBC Montreal", self.config, names, calls, "tv_logos", station_name_index=stations)
        self.assertEqual(result["path"], self.paths[0])

    def test_multiple_same_name_stations_remain_ambiguous(self):
        paths = ["countries/canada/local/cbc-toronto-cblt-ca.png",
                 "countries/canada/local/cbc-toronto-cxyz-ca.png"]
        stations = build_station_name_index(paths, "tv_logos")
        result = match_channel("CBC Toronto", self.config, {}, {}, "tv_logos", station_name_index=stations)
        self.assertEqual(result["reason"], "ambiguous")
        self.assertIsNone(result["path"])

    def test_conflicting_strong_evidence_is_skipped(self):
        result = self.match("CA | Global Montreal | CBLT", "countries/canada")
        self.assertEqual(result["reason"], "conflicting_matches")
        self.assertIsNone(result["path"])

    def test_scope_and_ambiguity_are_honored(self):
        self.assertIsNone(self.match("CA | Global Montreal | CKMI", "countries/canada/local")["path"])
        paths = self.paths + ["countries/united-kingdom/hd/bbc-one-hd-uk.png"]
        names = build_name_index(paths, "tv_logos", "countries/united-kingdom")
        result = match_channel("UK | BBC One", self.config, names, {}, "tv_logos")
        self.assertEqual(result["reason"], "ambiguous")

    def test_generic_network_fallback_requires_opt_in_and_keeps_numbers(self):
        paths = self.paths + ["countries/canada/ctv-2-ca.png"]
        scope = "countries/canada"
        names = build_name_index(paths, "tv_logos", scope)
        calls = build_callsign_index(paths, "tv_logos", scope)
        networks = build_network_index(paths, "tv_logos", scope)
        config = {**self.config, "generic_fallback": True}
        for channel, path in [("CA | CTV Toronto | CFTO", self.paths[5]),
                              ("CA | CTV 2 Toronto | CKVR", paths[-1]),
                              ("CA | City TV Toronto | CITY", self.paths[6])]:
            with self.subTest(channel=channel):
                result = match_channel(channel, config, names, calls, "tv_logos", networks)
                self.assertEqual(result["path"], path)
                self.assertEqual(result["method"], "network_fallback")
        no_ctv2 = build_network_index(self.paths, "tv_logos", scope)
        self.assertIsNone(match_channel("CA | CTV 2 Toronto | CKVR", config, names, calls, "tv_logos", no_ctv2)["path"])
        self.assertIsNone(match_channel("CA | CTV Toronto | CFTO", self.config, names, calls, "tv_logos", networks)["path"])

    def test_generic_fallback_is_scoped_and_does_not_treat_callsign_as_network(self):
        scope = "countries/canada/local"
        networks = build_network_index(self.paths, "tv_logos", scope)
        self.assertEqual(dict(networks), {})
        config = {**self.config, "generic_fallback": True}
        names = build_name_index(self.paths, "tv_logos", "countries/canada")
        calls = build_callsign_index(self.paths, "tv_logos", "countries/canada")
        networks = build_network_index(self.paths, "tv_logos", "countries/canada")
        self.assertIsNone(match_channel("CA | Unrelated Network | CITY", config, names, calls, "tv_logos", networks)["path"])
        for channel in ("CA | CTV Comedy", "CA | CTV Drama", "CA | CBC News"):
            with self.subTest(channel=channel):
                self.assertIsNone(match_channel(channel, config, names, calls, "tv_logos", networks)["path"])

    def test_generic_network_index_accepts_any_country_but_not_local_folders(self):
        paths = ["countries/australia/seven-au.png", "countries/australia/hd/seven-hd-au.png",
                 "countries/australia/local/seven-sydney-au.png", "countries/france/tf1.png",
                 "countries/canada/ctv-ca.png", "networks/australia/seven.png"]
        networks = build_network_index(paths, "tv_logos", "countries/australia")
        self.assertEqual({path for entries in networks.values() for _, path in entries}, set(paths[:2]))
        all_networks = build_network_index(paths, "tv_logos")
        self.assertIn((("tf", "1"), paths[3]), all_networks["tf"])
        self.assertNotIn(paths[2], {path for entries in all_networks.values() for _, path in entries})
        self.assertFalse(build_network_index(paths, "other"))

    def test_generic_fallback_uses_eligible_paths_outside_previous_countries(self):
        paths = ["countries/australia/seven-au.png"]
        names = build_name_index(paths, "tv_logos", "countries/australia")
        networks = build_network_index(paths, "tv_logos", "countries/australia")
        config = {**self.config, "generic_fallback": True}
        result = match_channel("AU | Seven Sydney | WXYZ", config, names, {}, "tv_logos", networks)
        self.assertEqual(result["path"], paths[0])
        self.assertEqual(result["method"], "network_fallback")
        self.assertIsNone(match_channel("AU | Seven Sydney", config, names, {}, "tv_logos", networks)["path"])
