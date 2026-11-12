import json
from pathlib import Path
import unittest

from src.callsign_matching import build_callsign_index
from src.matching_engine import match_channel
from src.name_matching import build_name_index
from fixture_variants import FIXTURES, VARIANTS, make_variants

US_STATIONS = {
    "WLS": "abc-7-wls", "WABC": "abc-7-wabc", "WJLA": "abc-7-wjla",
    "WBBM": "cbs-2-wbbm", "WCBS": "cbs-2-wcbs", "WUSA": "cbs-9-wusa",
    "WFLD": "fox-32-wfld", "WNYW": "fox-5-wnyw", "WTTG": "fox-5-wttg",
    "WMAQ": "nbc-5-wmaq", "WNBC": "nbc-4-wnbc", "WRC": "nbc-4-wrc",
}


class RegionalLineupTests(unittest.TestCase):
    def test_generated_lineup_variants_preserve_every_group_and_channel(self):
        original = json.loads((FIXTURES / "regional_lineup.json").read_text(encoding="utf-8"))
        expected = make_variants(original)
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                actual = json.loads((FIXTURES / f"regional_lineup.{variant}.json").read_text(encoding="utf-8"))
                self.assertEqual(actual, expected[variant])
                self.assertEqual({group: len(names) for group, names in actual.items()},
                                 {group: len(names) for group, names in original.items()})

    def test_lineup_variants_cover_distinct_realistic_formats(self):
        original = json.loads((FIXTURES / "regional_lineup.json").read_text(encoding="utf-8"))
        variants = make_variants(original)
        self.assertEqual(variants["region_dash"]["LOCALS - US"][0], "US - ABC Chicago - WLS")
        self.assertEqual(variants["region_colon"]["LOCALS - US"][0], "US: ABC Chicago (WLS)")
        self.assertEqual(variants["plain_parentheses"]["LOCALS - US"][0], "ABC Chicago (WLS)")
        self.assertEqual(variants["no_callsign"]["LOCALS - US"][0], "ABC Chicago")

    def test_fixture_contains_region_groups_and_names_only(self):
        fixture = json.loads((Path(__file__).parent / "fixtures" / "regional_lineup.json").read_text(encoding="utf-8"))
        self.assertEqual(set(fixture), {"ENTERTAINMENT - CA", "ENTERTAINMENT - UK", "ENTERTAINMENT - US",
                                       "LOCALS - CA", "LOCALS - US", "NEWS - CA", "NEWS - US",
                                       "SPORTS - CA", "SPORTS - QC", "SPORTS - UK", "SPORTS - US"})
        self.assertTrue(all(isinstance(name, str) and "http://" not in name and "https://" not in name
                            for channels in fixture.values() for name in channels))

    def test_us_locals_without_callsigns_use_corroborated_guide_hints(self):
        fixture = json.loads((Path(__file__).parent / "fixtures" / "regional_lineup.json").read_text(encoding="utf-8"))
        root = "countries/united-states/us-local/"
        paths = [f"{root}{stem}-us.png" for stem in US_STATIONS.values()]
        name_index = build_name_index(paths, "tv_logos", root)
        call_index = build_callsign_index(paths, "tv_logos", root)
        config = {"strategy": "callsign", "prefix": "", "prefix_mode": "literal", "variant": "strict",
                  "generic_fallback": False, "guide_signals": True, "threshold": 90}
        self.assertEqual(len(fixture["LOCALS - US"]), 12)
        for name in fixture["LOCALS - US"]:
            with self.subTest(name=name):
                stripped, token = name.rsplit(" | ", 1)
                direct = match_channel(name, config, name_index, call_index, "tv_logos")
                no_guide = match_channel(stripped, config, name_index, call_index, "tv_logos")
                # Synthetic guide IDs preserve no private provider metadata.
                guide = match_channel(stripped, config, name_index, call_index, "tv_logos", guide_id=f"{token}.us")
                self.assertEqual(direct["path"], f"{root}{US_STATIONS[token]}-us.png")
                self.assertIsNone(no_guide["path"])
                self.assertEqual(guide["path"], direct["path"])
                self.assertEqual(guide["method"], "guide_callsign")

    def test_us_local_variants_keep_expected_station_matches(self):
        original = json.loads((FIXTURES / "regional_lineup.json").read_text(encoding="utf-8"))
        variants = make_variants(original)
        root = "countries/united-states/us-local/"
        paths = [f"{root}{stem}-us.png" for stem in US_STATIONS.values()]
        names = build_name_index(paths, "tv_logos", root)
        calls = build_callsign_index(paths, "tv_logos", root)
        config = {"strategy": "callsign", "prefix": "", "prefix_mode": "literal", "variant": "strict",
                  "generic_fallback": False, "guide_signals": True, "threshold": 90}
        for variant in VARIANTS:
            for original_name, alternate in zip(original["LOCALS - US"], variants[variant]["LOCALS - US"]):
                token = original_name.rsplit(" | ", 1)[1]
                with self.subTest(variant=variant, name=alternate):
                    result = match_channel(alternate, config, names, calls, "tv_logos",
                                           guide_id=f"{token}.us" if variant == "no_callsign" else None)
                    self.assertEqual(result["path"], f"{root}{US_STATIONS[token]}-us.png")

    def test_guide_signal_requires_network_corroboration_and_is_optional(self):
        paths = ["countries/united-states/us-local/abc-7-wabc-us.png",
                 "countries/united-states/us-local/cbs-2-wcbs-us.png"]
        names = build_name_index(paths, "tv_logos")
        calls = build_callsign_index(paths, "tv_logos")
        config = {"strategy": "callsign", "prefix": "", "prefix_mode": "literal", "variant": "strict",
                  "generic_fallback": False, "guide_signals": True, "threshold": 90}
        self.assertIsNone(match_channel("US | ABC New York", config, names, calls, "tv_logos", guide_id="WCBS.us")["path"])
        self.assertIsNone(match_channel("US | ABC New York", {**config, "guide_signals": False}, names, calls,
                                       "tv_logos", guide_id="WABC.us")["path"])
        conflict = match_channel("US | ABC New York | WABC", config, names, calls, "tv_logos", guide_id="WCBS.us")
        # Non-corroborated guide metadata is ignored, not used as a canonical identity.
        self.assertEqual(conflict["path"], paths[0])
