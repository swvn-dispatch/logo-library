from contextlib import contextmanager
import unittest

from src.automatic_run import run_automatic


class Catalog:
    id = "tv_logos"
    accepts_legacy_paths = True

    def __init__(self):
        self.reads = 0

    def options(self, data_dir):
        self.reads += 1
        return ["countries/united-states/abc-us.png", "countries/united-states/news-us.png"]

    @contextmanager
    def resolve(self, data_dir, path):
        yield path


class AutomaticRunTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.settings = {"automatic_groups": [{"group": "1", "strategy": "exact", "catalog": "tv_logos",
                                               "scope": "countries/united-states"}]}
        self.calls = []

    def assign(self, *args):
        self.calls.append(args)

    def run_match(self, channels, assign=None):
        return run_automatic("/data", self.settings, channels, [1], [self.catalog], assign or self.assign)

    def test_hints_prefer_union_and_fall_back_with_original_name(self):
        self.catalog.options = lambda _: ["countries/canada/news-ca.png", "countries/united-states/news-us.png"]
        self.settings["automatic_groups"][0]["scope"] = "."
        self.settings["automatic_prefix"] = "CA | "
        self.settings["automatic_channel_hints"] = [
            {"mode": "starts_with", "text": "CA |", "path_mode": "contains", "path_text": "canada"},
            {"mode": "contains", "text": "news", "path_mode": "contains", "path_text": "missing"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "CA | News"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(self.calls[0][5], "tv_logos:countries/canada/news-ca.png")
        self.settings["catalog_filters"] = [{"mode": "exclude_contains", "text": "canada"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "CA | News"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(self.calls[-1][5], "tv_logos:countries/united-states/news-us.png")

    def test_ambiguous_hint_falls_back_to_normal_pool(self):
        from unittest.mock import patch
        self.settings["automatic_channel_hints"] = [{"mode": "contains", "text": "ABC", "path_mode": "contains", "path_text": "united"}]
        with patch("src.automatic_run.match_channel", side_effect=[{"reason": "ambiguous", "method": "name"},
                {"reason": None, "method": "name", "path": "countries/united-states/abc-us.png"}]) as match:
            result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertEqual(match.call_count, 2)
        self.assertEqual(result["applied"], 1)

    def test_matching_hint_rows_form_union_and_use_cached_indexes(self):
        from unittest.mock import patch
        import src.automatic_run as runner
        self.catalog.options = lambda _: ["countries/canada/news-ca.png", "countries/united-states/abc-us.png"]
        self.settings["automatic_groups"][0]["scope"] = "."
        self.settings["automatic_channel_hints"] = [
            {"mode": "contains", "text": "C", "path_mode": "contains", "path_text": "canada"},
            {"mode": "contains", "text": "C", "path_mode": "contains", "path_text": "united-states"}]
        with patch.object(runner, "build_name_index", wraps=runner.build_name_index) as build:
            result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"},
                                     {"id": 2, "group_id": 1, "name": "ABC"}])
        self.assertEqual(result["applied"], 2)
        self.assertEqual(build.call_count, 1)
        self.assertEqual(len(build.call_args.args[0]), 2)

    def test_below_threshold_hint_retries_and_reports_final_result(self):
        from unittest.mock import patch
        self.settings["automatic_channel_hints"] = [{"mode": "contains", "text": "ABC", "path_mode": "contains", "path_text": "united"}]
        with patch("src.automatic_run.match_channel", side_effect=[{"reason": "below_threshold", "method": "fuzzy"},
                {"reason": "no_match", "method": "none"}]) as match:
            result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertEqual(match.call_count, 2)
        self.assertEqual(result["channels"][0]["reason"], "no_match")

    def test_ignore_patterns_override_manual_and_invalid_rules_stop_matching(self):
        self.settings["mappings"] = [{"channel": "1", "logo": "tv_logos:a.png"}]
        self.settings["automatic_ignore_patterns"] = [{"mode": "regex", "text": "^abc$"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertEqual(result["ignored"], 1)
        self.assertEqual(self.calls, [])
        self.settings["automatic_ignore_patterns"] = [{"mode": "regex", "text": "["}]
        result = self.run_match([{"id": 2, "group_id": 1, "name": "ABC"}])
        self.assertTrue(result["configuration_errors"])
        self.assertEqual(self.calls, [])

    def test_report_candidates_respect_scope_and_include_similarity(self):
        self.catalog.options = lambda _: ["countries/united-states/news-us.png", "countries/canada/newsy-ca.png"]
        self.settings["automatic_groups"][0]["strategy"] = "fuzzy"
        self.settings["automatic_threshold"] = 100
        result = self.run_match([{"id": 1, "group_id": 1, "name": "Newsy"}])
        entry = result["channels"][0]
        self.assertEqual(entry["reason"], "below_threshold")
        self.assertEqual(entry["candidates"][0]["path"], "tv_logos:countries/united-states/news-us.png")
        self.assertGreater(entry["candidates"][0]["similarity"], 0)
        self.assertEqual(self.calls, [])

    def test_ambiguous_candidates_respect_catalog_filters(self):
        base = "countries/united-states/news-us.png"
        hd = "countries/united-states/hd/news-hd-us.png"
        horizontal = "countries/united-states/news-hz-us.png"
        self.catalog.options = lambda _: [base, hd, horizontal]
        self.settings["automatic_variant"] = "strict"
        self.settings["catalog_filters"] = [{"mode": "exclude_contains", "text": "/hd/"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "News"}])
        entry = result["channels"][0]
        self.assertEqual(entry["reason"], "ambiguous")
        self.assertEqual({c["path"] for c in entry["candidates"]}, {f"tv_logos:{base}", f"tv_logos:{horizontal}"})
        self.assertTrue(all("similarity" not in c for c in entry["candidates"]))
        self.assertEqual(self.calls, [])

    def test_applies_matches_once_and_caches_index(self):
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"},
                                 {"id": 2, "group_id": 1, "name": "News"}])
        self.assertEqual((result["applied"], result["skipped"], result["failed"]), (2, 0, 0))
        self.assertEqual(self.catalog.reads, 1)
        self.assertEqual(self.calls[0][5], "tv_logos:countries/united-states/abc-us.png")

    def test_skips_manual_existing_duplicate_and_no_match(self):
        self.settings["mappings"] = [{"channel": "1", "logo": ""}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"},
                                 {"id": 2, "group_id": 1, "name": "ABC", "logo_id": 8},
                                 {"id": 3, "group_id": None, "name": "ABC"},
                                 {"id": 4, "group_id": 1, "name": "Unknown"},
                                 {"id": 5, "group_id": 1, "name": "ABC"},
                                 {"id": 5, "group_id": 1, "name": "ABC"}])
        self.assertEqual([entry["reason"] for entry in result["channels"]],
                         ["manual_mapping_incomplete", "existing_logo", "no_match",
                          "duplicate_channel", "duplicate_channel"])
        self.assertEqual(result["skipped"], 5)
        self.assertEqual(self.calls, [])

    def test_manual_mappings_and_ignored_channels_are_successful(self):
        self.settings["mappings"] = [{"channel": "1", "logo": "tv_logos:old.png"},
                                     {"channel": "2", "ignore": True},
                                     {"channel": "3", "ignore": True, "logo": "old.png"}]
        result = self.run_match([{"id": i, "group_id": 1, "name": "ABC"} for i in (1, 2, 3)])
        self.assertEqual((result["applied"], result["preserved"], result["ignored"], result["skipped"]), (0, 1, 2, 0))
        self.assertEqual([row["status"] for row in result["channels"]], ["success", "success", "success"])
        self.assertEqual([row["outcome"] for row in result["channels"]], ["manual_mapping_preserved", "ignored", "ignored"])
        self.assertEqual(self.calls, [])

    def test_incomplete_duplicate_and_invalid_manual_rows_do_not_override_channels(self):
        self.settings["mappings"] = [{"channel": "1"}, {"channel": "2", "logo": "b.png"},
                                     {"channel": "2", "logo": "a.png"}, {"channel": "3", "ignore": "yes"}]
        result = self.run_match([{"id": i, "group_id": 1, "name": "ABC"} for i in (1, 2, 3)])
        self.assertEqual([row["reason"] for row in result["channels"]],
                         ["manual_mapping_incomplete", "manual_mapping_conflict", "manual_mapping_invalid"])
        self.assertEqual(result["skipped"], 3)
        self.assertEqual(self.calls, [])

    def test_auto_ignore_list_overrides_manual_and_legacy_rows(self):
        self.settings["automatic_ignored_channels"] = ["1", "2"]
        self.settings["mappings"] = [{"channel": "1", "logo": "a.png"},
                                     {"channel": "3", "ignore": True}]
        result = self.run_match([{"id": i, "group_id": 1, "name": "ABC"} for i in (1, 2, 3)])
        self.assertEqual((result["ignored"], result["preserved"], result["applied"]), (2, 0, 1))
        self.assertEqual([row.get("outcome") for row in result["channels"][:2]], ["ignored", "ignored"])
        self.assertEqual(self.calls[0][0], "3")

    def test_invalid_auto_ignore_list_fails_closed(self):
        for value in ("1", [None], [True], ["not-an-id"], [0]):
            with self.subTest(value=value):
                self.settings["automatic_ignored_channels"] = value
                result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
                self.assertEqual(result["applied"], 0)
                self.assertIn("Channels to ignore", result["configuration_errors"][0])
                self.assertEqual(self.calls, [])

    def test_manual_or_ignore_added_during_run_is_reported_as_success(self):
        def guard(channel, *args):
            return "manual_mapping" if channel == "1" else "ignored"
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"},
                                 {"id": 2, "group_id": 1, "name": "ABC"}], guard)
        self.assertEqual((result["preserved"], result["ignored"], result["skipped"]), (1, 1, 0))
        self.assertTrue(all(row["status"] == "success" for row in result["channels"]))

    def test_manual_mappings_remain_reported_when_filters_block_matching(self):
        self.settings["catalog_filters"] = [{"mode": "exclude_regex", "text": "["}]
        self.settings["mappings"] = [{"channel": "1", "logo": "tv_logos:old.png"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"},
                                 {"id": 2, "group_id": 1, "name": "ABC"}])
        self.assertEqual(result["preserved"], 1)
        self.assertEqual(result["channels"][0]["status"], "success")
        self.assertTrue(result["configuration_errors"])
        self.assertEqual(len(result["channels"]), 1)

    def test_guard_skip_and_failure_are_isolated(self):
        def assign(channel, *args):
            if channel == "1":
                return "settings_changed"
            if channel == "2":
                raise ValueError("write failed")

        result = self.run_match([{"id": i, "group_id": 1, "name": "ABC"} for i in (1, 2, 3)], assign)
        self.assertEqual((result["applied"], result["skipped"], result["failed"]), (1, 1, 1))
        self.assertEqual(result["channels"][0]["reason"], "settings_changed")
        self.assertEqual(result["channels"][1]["reason"], "write failed")

    def test_bad_configuration_and_manual_settings_fail_closed(self):
        self.settings["automatic_groups"] *= 2
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertEqual(len(result["configuration_errors"]), 2)
        self.assertEqual(result["channels"], [])
        self.assertEqual(result["skipped"], 0)
        self.settings["mappings"] = None
        with self.assertRaises(ValueError):
            self.run_match([])

    def test_disabled_unconfigured_and_missing_groups_are_omitted(self):
        self.settings["automatic_groups"].append({"group": "2", "strategy": "disabled"})
        self.settings["mappings"] = [{"channel": "3"}]
        channels = [{"id": 1, "group_id": 1, "name": "ABC"},
                    {"id": 2, "group_id": 2, "name": "ABC"},
                    {"id": 3, "group_id": 3, "name": "ABC"},
                    {"id": 4, "group_id": None, "name": "ABC"},
                    {"id": 5, "group_id": 99, "name": "ABC"}]
        result = run_automatic("/data", self.settings, channels, [1, 2, 3], [self.catalog], self.assign)
        self.assertEqual((result["applied"], result["skipped"], result["failed"]), (1, 0, 0))
        self.assertEqual([row["channel"] for row in result["channels"]], ["1"])

    def test_replace_policy_and_fuzzy_report(self):
        self.settings["automatic_groups"][0].update(strategy="fuzzy", replace=True)
        self.settings["automatic_threshold"] = 99
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABCD", "logo_id": 2}])
        self.assertEqual(result["channels"][0]["reason"], "below_threshold")
        self.assertLess(result["channels"][0]["score"], 99)

    def test_missing_scope_is_a_configuration_error(self):
        self.settings["automatic_groups"][0]["scope"] = "united-states"
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertIn("scope contains no indexed logos", result["configuration_errors"][0])
        self.assertEqual(result["channels"], [])
        self.assertEqual(self.calls, [])

    def test_group_regex_prefix_is_used_end_to_end(self):
        self.settings["automatic_prefix_rules"] = [{"group": "1", "mode": "regex", "prefix": r"^(?:US|CA)\s*\|\s*"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "CA | ABC"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(self.calls[0][4]["prefix_mode"], "regex")

    def test_generic_fallback_is_guarded_and_reported(self):
        self.settings["automatic_generic_fallback"] = True
        result = self.run_match([{"id": 1, "group_id": 1, "name": "US | ABC Chicago | WLS"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(result["channels"][0]["method"], "network_fallback")
        self.assertTrue(self.calls[0][4]["generic_fallback"])

    def test_station_name_index_is_used_by_run(self):
        self.catalog.options = lambda data_dir: ["countries/canada/cbc-toronto-ca.png",
                                                "countries/canada/local/cbc-toronto-cblt-ca.png"]
        self.settings["automatic_groups"][0]["scope"] = "countries/canada"
        result = self.run_match([{"id": 1, "group_id": 1, "name": "CBC Toronto"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(result["channels"][0]["method"], "station_name")
        self.assertEqual(self.calls[0][5], "tv_logos:countries/canada/local/cbc-toronto-cblt-ca.png")

    def test_entire_catalog_respects_include_filters(self):
        self.settings["automatic_groups"][0]["scope"] = "."
        self.catalog.options = lambda data_dir: ["countries/united-states/abc-us.png", "countries/canada/abc-ca.png"]
        self.settings["catalog_filters"] = [{"mode": "include_starts_with", "text": "countries/canada/"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(self.calls[0][5], "tv_logos:countries/canada/abc-ca.png")
        self.assertEqual(self.calls[0][4]["catalog_filters"], self.settings["catalog_filters"])

    def test_excluded_logos_do_not_match_even_when_scope_has_other_logos(self):
        self.settings["catalog_filters"] = [{"mode": "exclude_contains", "text": "abc"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertEqual(result["channels"][0]["reason"], "no_match")
        self.assertEqual(self.calls, [])

    def test_include_and_exclude_filters_apply_before_variant_resolution(self):
        self.settings["automatic_groups"][0]["scope"] = "."
        self.catalog.options = lambda data_dir: ["countries/united-states/abc-us.png",
                                                 "countries/united-states/abc-hd-us.png",
                                                 "countries/canada/abc-ca.png"]
        self.settings["catalog_filters"] = [
            {"mode": "include_starts_with", "text": "countries/united-states/"},
            {"mode": "exclude_contains", "text": "-hd-"},
        ]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(self.calls[0][5], "tv_logos:countries/united-states/abc-us.png")

    def test_filtered_out_scope_reports_configuration_error(self):
        self.settings["catalog_filters"] = [{"mode": "include_contains", "text": "canada"}]
        result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
        self.assertIn("after catalog filters", result["configuration_errors"][0])
        self.assertEqual(result["channels"], [])

    def test_invalid_filters_do_not_widen_automatic_matching(self):
        for row in ({"mode": "exclude_regex", "text": "["},
                    {"mode": "include_contains", "text": "us", "catalog": "missing"}):
            with self.subTest(row=row):
                self.settings["catalog_filters"] = [row]
                result = self.run_match([{"id": 1, "group_id": 1, "name": "ABC"}])
                self.assertEqual(result["applied"], 0)
                self.assertTrue(result["configuration_errors"])
                self.assertEqual(result["channels"], [])
                self.assertEqual(self.calls, [])
