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

    def test_user_guide_group_counts_and_strategy_equivalence(self):
        expected_counts = {
            "LOCALS - US": (12, 12), "LOCALS - CA": (4, 4),
            "ENTERTAINMENT - US": (14, 22), "NEWS - US": (6, 8), "SPORTS - US": (5, 6),
            "ENTERTAINMENT - UK": (4, 19), "SPORTS - UK": (0, 15),
            "ENTERTAINMENT - CA": (9, 10), "NEWS - CA": (4, 5), "SPORTS - CA": (0, 12),
            "SPORTS - QC": (1, 5),
        }
        config = {**self.config, "generic_fallback": False, "guide_signals": False}
        for group, channels in self.original.items():
            country, _ = REGIONS[group.rsplit(" - ", 1)[1]]
            names, calls, networks, station_names = self.indices[country]
            counts = []
            for variant in ("strict", "standard"):
                paths = []
                for channel in channels:
                    args = {**config, "strategy": "exact", "variant": variant}
                    result = match_channel(channel, args, names, calls, "tv_logos", networks,
                                           station_name_index=station_names)
                    paths.append(result["path"])
                counts.append(sum(path is not None for path in paths))
            self.assertEqual(tuple(counts), expected_counts[group], group)

        for filename in FORMATS:
            lineup = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
            for group, channels in lineup.items():
                country, _ = REGIONS[group.rsplit(" - ", 1)[1]]
                names, calls, networks, station_names = self.indices[country]
                for channel in channels:
                    with self.subTest(format=filename, group=group, channel=channel):
                        args = {**config, "strategy": "exact"}
                        exact = match_channel(channel, args, names, calls, "tv_logos", networks,
                                              station_name_index=station_names)
                        callsign = match_channel(channel, {**args, "strategy": "callsign"}, names, calls,
                                                 "tv_logos", networks, station_name_index=station_names)
                        self.assertEqual(exact["path"], callsign["path"])

    def test_user_guide_local_scope_comparison(self):
        config = {**self.config, "generic_fallback": False, "guide_signals": False}
        for group, scope, expected in (("LOCALS - US", "countries/united-states/us-local", 12),
                                       ("LOCALS - CA", "countries/canada/local", 2),
                                       ("LOCALS - CA", "countries/canada", 4)):
            names = build_name_index(self.paths, "tv_logos", scope)
            calls = build_callsign_index(self.paths, "tv_logos", scope)
            networks = build_network_index(self.paths, "tv_logos", scope)
            station_names = build_station_name_index(self.paths, "tv_logos", scope)
            count = sum(bool(match_channel(channel, config, names, calls, "tv_logos", networks,
                                           station_name_index=station_names)["path"])
                        for channel in self.original[group])
            with self.subTest(group=group, scope=scope):
                self.assertEqual(count, expected)
