"""Evaluate every lineup format against reviewed catalog-path expectations."""

import json
from pathlib import Path
import unittest

from src.callsign_matching import build_callsign_index, build_station_name_index
from src.matching_engine import build_network_index, match_channel
from src.name_matching import build_name_index

FIXTURES = Path(__file__).parent / "fixtures"
FORMATS = ("regional_lineup.json", "regional_lineup.region_dash.json", "regional_lineup.region_colon.json",
           "regional_lineup.plain_parentheses.json", "regional_lineup.no_callsign.json")
REGIONS = {"CA": ("canada", "ca"), "QC": ("canada", "ca"),
           "US": ("united-states", "us"), "UK": ("united-kingdom", "uk")}


class RegionalMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((FIXTURES / FORMATS[0]).read_text(encoding="utf-8"))
        cls.expected = json.loads((FIXTURES / "regional_expected.json").read_text(encoding="utf-8"))
        cls.paths = json.loads((FIXTURES / "catalog_paths.regional.json").read_text(encoding="utf-8"))["paths"]
        cls.indices = {}
        for country in ("canada", "united-states", "united-kingdom"):
            scope = f"countries/{country}"
            cls.indices[country] = (build_name_index(cls.paths, "tv_logos", scope),
                                    build_callsign_index(cls.paths, "tv_logos", scope),
                                    build_network_index(cls.paths, "tv_logos", scope),
                                    build_station_name_index(cls.paths, "tv_logos", scope))
        cls.config = {"strategy": "exact", "prefix": "", "prefix_mode": "literal", "variant": "standard",
                      "generic_fallback": True, "guide_signals": True, "threshold": 90}

    def test_all_formats_against_expected_logos(self):
        self.assertEqual(set(self.expected), set(self.original))
        for filename in FORMATS:
            lineup = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
            self.assertEqual(set(lineup), set(self.original))
            for group, channel_names in lineup.items():
                expected_stems = self.expected[group]
                self.assertEqual(len(channel_names), len(expected_stems), group)
                country, suffix = REGIONS[group.rsplit(" - ", 1)[1]]
                names, calls, networks, station_names = self.indices[country]
                for position, channel_name in enumerate(channel_names):
                    stem = expected_stems[position]
                    generic = isinstance(stem, str) and stem.startswith("generic:")
                    if generic:
                        stem = stem.removeprefix("generic:")
                    # Without the original call sign, generic network fallback
                    # intentionally cannot infer that this is a local station.
                    expected = None if stem is None or (generic and filename.endswith("no_callsign.json")) else (
                        f"countries/{country}/{stem}-{suffix}.png")
                    if expected:
                        self.assertIn(expected, self.paths)
                    original_name = self.original[group][position]
                    parts = original_name.split(" | ")
                    guide = f"{parts[-1]}.us" if group == "LOCALS - US" and len(parts) == 3 else None
                    with self.subTest(format=filename, group=group, channel=channel_name):
                        result = match_channel(channel_name, self.config, names, calls, "tv_logos", networks,
                                               guide, station_names)
                        self.assertEqual(result["path"], expected, result)
                        if expected and generic:
                            self.assertEqual(result["method"], "network_fallback")

    def test_default_safety_options_never_choose_an_unexpected_logo(self):
        config = {**self.config, "variant": "strict", "generic_fallback": False, "guide_signals": False}
        for filename in FORMATS:
            lineup = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
            for group, channel_names in lineup.items():
                country, suffix = REGIONS[group.rsplit(" - ", 1)[1]]
                names, calls, networks, station_names = self.indices[country]
                for channel_name, stem in zip(channel_names, self.expected[group]):
                    with self.subTest(format=filename, group=group, channel=channel_name):
                        result = match_channel(channel_name, config, names, calls, "tv_logos", networks,
                                               station_name_index=station_names)
                        if result["path"] is not None:
                            self.assertIsNotNone(stem, result)
                            self.assertFalse(stem.startswith("generic:"), result)
                            self.assertEqual(result["path"], f"countries/{country}/{stem}-{suffix}.png", result)
