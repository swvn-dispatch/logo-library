import json
import shutil
from pathlib import Path
import tempfile
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from src import Plugin
from src.fields import make_fields
from src.catalogs import catalog_actions
from src.catalogs.tv_logos import TvLogosCatalog
from src.catalogs.tv_logos.catalog import INDEX_NAME, current_catalog, read_index, update_catalog
from test_catalog import archive, opener


class PluginTests(unittest.TestCase):
    def setUp(self):
        lock = patch("src.action_lock", return_value=nullcontext(True))
        lock.start()
        self.addCleanup(lock.stop)

    def test_fields_use_discovery_context_without_creating_data_dir(self):
        with tempfile.TemporaryDirectory() as root:
            data_dir = Path(root) / "not-created"
            settings = {"automatic_ignored_channels": ["7"]}
            with patch("src.channel_options", return_value=[]), patch("src.group_options", return_value=[]):
                fields = Plugin().get_fields({"data_dir": str(data_dir), "settings": settings})
            self.assertFalse(data_dir.exists())
            ignored = next(field for field in fields if field["id"] == "automatic_ignored_channels")
            self.assertEqual(ignored["default"], ["7"])

    def test_automatic_assignment_uses_context_paths_and_host_directory(self):
        report = {"applied": 1, "skipped": 0, "failed": 0, "configuration_errors": [], "channels": []}
        def run(data_dir, settings, channels, groups, catalogs, assign):
            assign("1", "2", "Example", None, {}, "tv_logos:a.png", Path("/image"))
            return report
        ensure = unittest.mock.Mock(return_value="/host/logos")
        with patch("src.group_options", return_value=[]), patch("src.automatic_channels", return_value=[]), \
             patch("src.run_automatic", side_effect=run), patch("src.guarded_assign_logo") as guard, \
             patch("src.assign_logo") as assign:
            Plugin().run("run_automatic", {}, {"data_dir": "/stable", "code_dir": "/installed/code", "settings": {},
                                               "dispatcharr": {"ensure_directory": ensure}})
            self.assertEqual(guard.call_args.args[0], "/installed/code")
            guard.call_args.kwargs["assign"]("1", "tv_logos:a.png", Path("/image"))
        ensure.assert_called_once_with("logos")
        assign.assert_called_once_with("1", "tv_logos:a.png", Path("/image"), "/host/logos")

    def test_manifest_contract(self):
        manifest = json.loads((Path(__file__).parents[1] / "src" / "plugin.json").read_text())
        self.assertEqual(manifest["manifest_version"], 2)
        self.assertEqual({action["id"] for action in manifest["actions"]}, {"update_catalog", "apply_changes", "run_automatic", "ignore_skipped"})
        self.assertTrue(all(action.get("async") for action in manifest["actions"] if action["id"] != "ignore_skipped"))
        self.assertEqual(manifest["actions"][0]["id"], "apply_changes")
        manifest_actions = {action["id"]: action for action in manifest["actions"]}
        declared = catalog_actions()
        self.assertEqual(len({action["id"] for action in declared}), len(declared))
        self.assertNotIn("apply_changes", {action["id"] for action in declared})
        self.assertEqual(set(manifest_actions) - {"apply_changes", "run_automatic", "ignore_skipped"}, {action["id"] for action in declared})
        for action in declared:
            self.assertEqual(manifest_actions[action["id"]], action)
        self.assertEqual(manifest_actions["update_catalog"]["button_color"], "teal")
        self.assertEqual(manifest_actions["update_catalog"]["button_label"], "Refresh")
        self.assertEqual(manifest_actions["ignore_skipped"]["button_label"], "Ignore")
        self.assertEqual(manifest_actions["apply_changes"]["button_label"], "Manual Match")
        self.assertEqual(manifest_actions["run_automatic"]["button_label"], "Auto Match")

    def test_missing_selections_remain_options(self):
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, {"mappings": [{"channel": "123", "logo": "old/a.png"}]}, [])
            by_id = {field["id"]: field for field in fields}
            self.assertIn("Reload plugin", by_id["instructions"]["description"])
            columns = by_id["mappings"]["columns"]
            self.assertEqual(columns[0]["options"][0]["value"], "123")
            self.assertEqual(columns[1]["options"][0]["value"], "old/a.png")

    def test_settings_sections_and_top_notice(self):
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, {}, [])
        self.assertEqual([field["id"] for field in fields], [
            "instructions", "manual_assignment", "manual_instructions", "mappings",
            "automatic_assignment", "automatic_setup_help", "automatic_group_help",
            "automatic_groups", "automatic_ignored_channels", "automatic_advanced", "automatic_prefix",
            "automatic_prefix_mode", "automatic_threshold", "automatic_variant", "automatic_generic_fallback",
            "automatic_guide_signals", "catalog_filters_section",
            "catalog_filter_instructions", "catalog_filters",
            "scheduled_tasks", "scheduled_tasks_help", "schedule_automatic_mode", "schedule_automatic_value",
            "schedule_catalog_mode", "schedule_catalog_value",
        ])
        by_id = {field["id"]: field for field in fields}
        self.assertNotIn("section", by_id["instructions"])
        self.assertEqual(by_id["manual_assignment"]["type"], "section")
        self.assertEqual(by_id["manual_instructions"]["section"], "manual_assignment")
        self.assertEqual(by_id["mappings"]["section"], "manual_assignment")
        self.assertEqual([column["id"] for column in by_id["mappings"]["columns"]], ["channel", "logo"])
        self.assertEqual(by_id["automatic_ignored_channels"]["type"], "multiselect")
        self.assertEqual(by_id["automatic_assignment"]["type"], "section")
        self.assertEqual(by_id["automatic_setup_help"]["section"], "automatic_assignment")
        self.assertIn("review the results for channels that were skipped or failed", by_id["automatic_setup_help"]["description"])
        self.assertIn("Catalog filters still apply", by_id["automatic_group_help"]["description"])
        self.assertIn("Replace: Allows Auto Match to overwrite existing channel logos.", by_id["automatic_group_help"]["description"])
        self.assertFalse(any(field["id"].startswith("automatic_default_") for field in fields))
        self.assertTrue(by_id["automatic_advanced"]["collapsed"])
        self.assertEqual(by_id["automatic_advanced"]["label"], "Automatic assignment - Advanced")
        self.assertNotIn("automatic_prefix_rules", by_id)
        self.assertEqual([column["id"] for column in by_id["automatic_groups"]["columns"]],
                         ["group", "strategy", "scope", "replace"])
        self.assertEqual(by_id["automatic_groups"]["columns"][0]["label"], "Group")
        strategy_options = by_id["automatic_groups"]["columns"][1]["options"]
        self.assertEqual([(option["value"], option["label"]) for option in strategy_options], [
            ("disabled", "Disabled"), ("exact", "Standard"), ("fuzzy", "Standard + fuzzy"),
        ])
        self.assertEqual(by_id["automatic_threshold"]["default"], 90)
        self.assertEqual(by_id["automatic_groups"]["columns"][-1]["label"], "Replace")
        self.assertEqual(by_id["automatic_variant"]["default"], "strict")
        self.assertFalse(by_id["automatic_generic_fallback"]["default"])
        self.assertFalse(by_id["automatic_guide_signals"]["default"])
        self.assertTrue(by_id["catalog_filters_section"]["collapsed"])
        self.assertTrue(by_id["scheduled_tasks"]["collapsed"])
        self.assertEqual(by_id["schedule_automatic_mode"]["default"], "disabled")
        self.assertEqual(by_id["schedule_catalog_mode"]["default"], "disabled")
        self.assertEqual(by_id["catalog_filters"]["section"], "catalog_filters_section")
        self.assertEqual([column["id"] for column in by_id["catalog_filters"]["columns"]], ["mode", "text"])
        self.assertEqual(len(by_id["catalog_filters"]["columns"][0]["options"]), 8)

    def test_legacy_ignored_channels_are_offered_for_migration(self):
        settings = {"mappings": [{"channel": "1", "ignore": True}, {"channel": "9", "ignore": True}]}
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, settings, [{"value": "1", "label": "First"}])
        by_id = {field["id"]: field for field in fields}
        select = by_id["automatic_ignored_channels"]
        self.assertEqual(select["default"], ["1", "9"])
        self.assertIn({"value": "9", "label": "Missing channel"}, select["options"])
        self.assertIn("First", by_id["manual_legacy_ignore"]["description"])
        settings["automatic_ignored_channels"] = []
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, settings, [{"value": "1", "label": "First"}])
        self.assertEqual(next(field for field in fields if field["id"] == "automatic_ignored_channels")["default"], [])

    def test_existing_prefix_rules_remain_editable(self):
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, {"automatic_prefix_rules": [{"group": "1", "prefix": "US"}]}, [], [])
        by_id = {field["id"]: field for field in fields}
        self.assertEqual(by_id["automatic_prefix_rules"]["section"], "automatic_advanced")
        self.assertIn("Remove all rows", by_id["automatic_prefix_help"]["description"])

    def test_saved_station_strategy_remains_selectable(self):
        with tempfile.TemporaryDirectory() as root:
            settings = {"automatic_groups": [{"group": "1", "strategy": "callsign"}]}
            fields = make_fields(root, settings, [], [{"value": "1", "label": "Locals"}])
        table = next(field for field in fields if field["id"] == "automatic_groups")
        options = table["columns"][1]["options"]
        self.assertIn({"value": "callsign", "label": "Standard (legacy station hint)"}, options)

    def test_legacy_shared_groups_do_not_add_controls_or_notices(self):
        settings = {"automatic_default_groups": ["1", "2"],
                    "automatic_groups": [{"group": "2", "strategy": "disabled"}]}
        options = [{"value": "1", "label": "Locals"}, {"value": "2", "label": "News"}]
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, settings, [], options)
            self.assertFalse(any(field["id"].startswith("automatic_default_") or
                                 field["id"] == "automatic_legacy_shared" for field in fields))

    def test_automatic_group_options_preserve_missing_groups(self):
        settings = {"automatic_groups": [{"group": "1"}, {"group": "9"}, {"group": "9"}]}
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, settings, [], [{"value": "1", "label": "Renamed"}])
        table = next(field for field in fields if field["id"] == "automatic_groups")
        self.assertEqual(table["columns"][0]["options"], [{"value": "1", "label": "Renamed"}])
        notice = next(field for field in fields if field["id"] == "automatic_missing_groups")
        self.assertIn("9", notice["description"])

    def test_scope_options_use_indexed_directories_and_keep_missing_values(self):
        class Catalog:
            id = label = "example"
            def options(self, data_dir):
                return ["countries/us/abc.png", "countries/us/local/station.png"]
        with tempfile.TemporaryDirectory() as root, patch("src.catalogs.CATALOGS", (Catalog(),)):
            fields = make_fields(root, {"automatic_groups": [{"scope": "us"}]}, [], [])
        table = next(field for field in fields if field["id"] == "automatic_groups")
        scope = next(column for column in table["columns"] if column["id"] == "scope")
        self.assertEqual(scope["type"], "select")
        self.assertIn({"value": ".", "label": "Entire catalog"}, scope["options"])
        self.assertIn({"value": "countries/us/local", "label": "countries/us/local"}, scope["options"])
        self.assertIn({"value": "us", "label": "Unavailable or filtered: us"}, scope["options"])

    def test_filters_limit_scope_directories_but_preserve_saved_selections(self):
        class Catalog:
            id = label = "example"
            accepts_legacy_paths = True

            def options(self, data_dir):
                return ["countries/canada/a.png", "countries/canada/local/b.png", "countries/us/c.png"]

        settings = {"catalog_filters": [{"mode": "include_contains", "text": "CANADA"},
                                        {"mode": "exclude_contains", "text": "/local/"}],
                    "automatic_groups": [{"group": "1", "scope": "countries/us"}]}
        with tempfile.TemporaryDirectory() as root, patch("src.catalogs.CATALOGS", (Catalog(),)):
            fields = make_fields(root, settings, [], [{"value": "1", "label": "Group"}])
        table = next(field for field in fields if field["id"] == "automatic_groups")
        options = next(column for column in table["columns"] if column["id"] == "scope")["options"]
        self.assertIn({"value": "countries/canada", "label": "countries/canada"}, options)
        self.assertNotIn("countries/canada/local", [option["value"] for option in options])
        self.assertIn({"value": "countries/us", "label": "Unavailable or filtered: countries/us"}, options)
        self.assertIn({"value": ".", "label": "Entire catalog"}, options)

    def test_field_select_options_have_nonempty_values(self):
        with tempfile.TemporaryDirectory() as root:
            fields = make_fields(root, {}, [])
        for field in fields:
            for item in [field, *field.get("columns", [])]:
                for option in item.get("options", []):
                    with self.subTest(field=field["id"], option=option):
                        self.assertIsInstance(option["value"], str)
                        self.assertTrue(option["value"])

    def test_filters_keep_saved_logo_and_report_invalid_regex(self):
        class Catalog:
            id = "example"
            label = "Example"
            accepts_legacy_paths = True

            def options(self, data_dir):
                return ["countries/canada/a.png", "countries/us/b.png", "countries/france/c.png"]

        settings = {
            "catalog_filters": [{"mode": "include_contains", "text": "CANADA"},
                                {"mode": "exclude_regex", "text": "["}],
            "mappings": [{"channel": "1", "logo": "example:countries/us/b.png"}],
        }
        with tempfile.TemporaryDirectory() as root, patch("src.catalogs.CATALOGS", (Catalog(),)):
            fields = make_fields(root, settings, [])
        by_id = {field["id"]: field for field in fields}
        options = by_id["mappings"]["columns"][1]["options"]
        self.assertEqual([item["value"] for item in options],
                         ["example:countries/canada/a.png", "example:countries/us/b.png"])
        self.assertEqual(options[1]["label"], "Example / countries/us/b.png")
        self.assertIn("Row 2", by_id["catalog_filter_errors"]["description"])

    def test_leader_initial_download_is_queued_only_when_missing(self):
        plugin = Plugin()
        calls = []
        with tempfile.TemporaryDirectory() as root:
            with patch("src.catalogs.tv_logos.current_catalog", return_value=None), \
                 patch("src.catalogs.tv_logos.read_index", return_value=None):
                plugin.on_leader_acquired({"data_dir": root, "dispatch_task": lambda *args: calls.append(args)})
            with patch("src.catalogs.tv_logos.current_catalog", return_value=Path(root)), \
                 patch("src.catalogs.tv_logos.read_index", return_value=["a.png"]):
                plugin.on_leader_acquired({"data_dir": root, "dispatch_task": lambda *args: calls.append(args)})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "update_catalog")
        self.assertTrue(calls[0][1]["initial"])
        self.assertTrue(calls[0][1]["request_token"])

    def test_existing_catalog_is_indexed_by_debounced_leader_task(self):
        catalog = TvLogosCatalog()
        calls = []
        with tempfile.TemporaryDirectory() as root:
            update_catalog(root, opener(archive([("root/a.png", b"image")])), remove_directory=shutil.rmtree)
            snapshot = current_catalog(root)
            (snapshot / INDEX_NAME).unlink()
            context = {"data_dir": root, "dispatch_task": lambda *args: calls.append(args),
                       "dispatcharr": {"remove_directory": shutil.rmtree}}
            catalog.on_leader_acquired(context)
            catalog.on_leader_acquired(context)
            self.assertEqual(len(calls), 1)
            self.assertEqual(catalog.options(root), [])
            result = catalog.run(calls[0][0], calls[0][1], context)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(read_index(snapshot), ["a.png"])
            self.assertEqual(catalog.options(root), ["a.png"])
            catalog.on_leader_acquired(context)
            self.assertEqual(len(calls), 1)

    def test_failed_dispatch_releases_debounce_reservation(self):
        catalog = TvLogosCatalog()
        with tempfile.TemporaryDirectory() as root:
            def fail(*args):
                raise RuntimeError("queue unavailable")

            with self.assertRaises(RuntimeError):
                catalog.on_leader_acquired({"data_dir": root, "dispatch_task": fail})
            calls = []
            catalog.on_leader_acquired({"data_dir": root, "dispatch_task": lambda *args: calls.append(args)})
            self.assertEqual(len(calls), 1)

    def test_action_reports_partial_result(self):
        with patch("src.group_options", return_value=[]), patch("src.automatic_channels", return_value=[{"id": 44, "number": "10.5", "name": "Test"}]), patch("src.apply_mappings", return_value={"applied": 1, "skipped": 1, "errors": [
            {"row": 2, "channel": "44", "message": "missing"}
        ]}):
            result = Plugin().run("apply_changes", {}, {"data_dir": "/x", "settings": {"mappings": []}})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["message"], "Applied 1, ignored 0, skipped 1.")
        self.assertEqual(result["errors"][0]["channel"], "10.5")

    def test_manual_match_keeps_saved_mappings_despite_filters(self):
        settings = {"mappings": [{"channel": "1", "logo": "tv_logos:countries/us/a.png"}],
                    "catalog_filters": [{"mode": "include_contains", "text": "canada"}],
                    "automatic_ignored_channels": ["1"]}
        with patch("src.group_options", return_value=[]), \
             patch("src.apply_mappings", return_value={"applied": 1, "skipped": 0, "errors": []}) as apply:
            result = Plugin().run("apply_changes", {}, {"data_dir": "/x", "settings": settings,
                                   "dispatcharr": {"ensure_directory": lambda name: "/logos"}})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(apply.call_args.args[1], settings["mappings"])

    def test_manual_match_can_assign_an_auto_ignored_channel(self):
        from contextlib import nullcontext

        class Catalog:
            id = "tv_logos"
            accepts_legacy_paths = True

            def resolve(self, data_dir, path):
                return nullcontext(Path("/catalog/logo.png"))

        settings = {"mappings": [{"channel": "1", "logo": "tv_logos:logo.png"}],
                    "automatic_ignored_channels": ["1"]}
        with patch("src.group_options", return_value=[]), patch("src.assign_logo") as assign, \
             patch("src.catalogs.CATALOGS", (Catalog(),)):
            result = Plugin().run("apply_changes", {}, {"data_dir": "/x", "settings": settings,
                                   "dispatcharr": {"ensure_directory": lambda name: "/logos"}})
        self.assertEqual(result["applied"], 1)
        self.assertEqual(result["status"], "ok")
        assign.assert_called_once_with("1", "tv_logos:logo.png", Path("/catalog/logo.png"), "/logos")

    def test_automatic_action_reports_details(self):
        report = {"applied": 0, "skipped": 1, "failed": 0, "configuration_errors": [],
                  "channels": [{"channel": "1", "name": "Test", "status": "skipped", "reason": "manual_mapping"}]}
        with patch("src.group_options", return_value=[]), patch("src.automatic_channels", return_value=[{"id": 1, "number": "42", "name": "Test"}]), \
             patch("src.store_skipped_ids", return_value="a" * 32), \
             patch("src.run_automatic", return_value=report):
            result = Plugin().run("run_automatic", {}, {"data_dir": "/x", "code_dir": "/plugin", "settings": {}})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["message"], "Applied 0, manual mappings preserved 0, ignored 0, skipped 1, failed 0.")
        self.assertEqual(result["channels"][0]["channel"], "42")
        self.assertEqual(result["channels"][0]["reason"], "manual_mapping")

    def test_automatic_action_reports_generic_fallback_count(self):
        report = {"applied": 1, "skipped": 0, "failed": 0, "configuration_errors": [],
                  "channels": [{"channel": "1", "name": "Test", "status": "applied", "method": "network_fallback"}]}
        with patch("src.group_options", return_value=[]), patch("src.automatic_channels", return_value=[]), \
             patch("src.run_automatic", return_value=report):
            result = Plugin().run("run_automatic", {}, {"data_dir": "/x", "settings": {}})
        self.assertIn("Generic network logos applied: 1", result["message"])

    def test_automatic_results_use_numbers_but_store_distinct_channel_ids(self):
        channels = [{"id": 101, "number": "7", "name": "A"},
                    {"id": 202, "number": "7", "name": "B"},
                    {"id": 303, "number": None, "name": "C"}]
        report = {"applied": 0, "skipped": 2, "failed": 1, "configuration_errors": ["Bad group"],
                  "channels": [{"channel": str(c["id"]), "name": c["name"],
                                "status": "failed" if c["id"] == 303 else "skipped", "reason": "no_match"}
                               for c in channels]}
        with patch("src.group_options", return_value=[]), patch("src.automatic_channels", return_value=channels), \
             patch("src.store_skipped_ids", return_value="a" * 32) as store, patch("src.run_automatic", return_value=report):
            result = Plugin().run("run_automatic", {}, {"data_dir": "/x", "code_dir": "/plugin", "settings": {"automatic_ignored_channels": ["101"]}})
        self.assertEqual([row["channel"] for row in result["channels"]], ["7", "7", None])
        self.assertEqual(store.call_args.args[1], ["101", "202", "303"])
        self.assertEqual(result["configuration"]["ignored_channels"], [{"number": "7", "name": "A"}])
        self.assertEqual(result["configuration_errors"], ["Bad group"])
        self.assertNotIn("101", json.dumps(result))
        self.assertNotIn("Bad group", result["message"])

    def test_automatic_action_reports_preserved_and_ignored_as_success(self):
        report = {"applied": 0, "preserved": 1, "ignored": 1, "skipped": 0, "failed": 0,
                  "configuration_errors": [], "channels": [
                      {"channel": "1", "name": "A", "status": "success", "outcome": "manual_mapping_preserved"},
                      {"channel": "2", "name": "B", "status": "success", "outcome": "ignored"}]}
        with patch("src.group_options", return_value=[]), patch("src.automatic_channels", return_value=[]), \
             patch("src.run_automatic", return_value=report):
            result = Plugin().run("run_automatic", {}, {"data_dir": "/x", "settings": {}})
        self.assertEqual(result["status"], "ok")
        self.assertIn("manual mappings preserved 1, ignored 1", result["message"])
        self.assertEqual(result["channels"][0]["status"], "success")

    def test_manual_mapping_alone_does_not_make_real_auto_run_partial(self):
        class Catalog:
            id = "tv_logos"
            accepts_legacy_paths = True

            def options(self, data_dir):
                return ["countries/canada/abc-ca.png"]

        settings = {"automatic_groups": [{"group": "1", "strategy": "exact", "scope": "countries/canada"}],
                    "mappings": [{"channel": "1", "logo": "tv_logos:countries/canada/abc-ca.png"}]}
        channels = [{"id": 1, "group_id": 1, "name": "ABC"}]
        with patch("src.group_options", return_value=[{"value": "1", "label": "Group"}]), \
             patch("src.automatic_channels", return_value=channels), patch("src.catalogs.CATALOGS", (Catalog(),)):
            result = Plugin().run("run_automatic", {}, {"data_dir": "/x", "settings": settings})
        self.assertEqual(result["status"], "ok")
        self.assertEqual((result["preserved"], result["skipped"]), (1, 0))
        self.assertEqual(result["channels"][0]["outcome"], "manual_mapping_preserved")

    def test_manual_action_ignore_is_not_partial(self):
        report = {"applied": 0, "ignored": 1, "skipped": 0, "errors": []}
        with patch("src.group_options", return_value=[]), patch("src.apply_mappings", return_value=report):
            result = Plugin().run("apply_changes", {}, {"data_dir": "/x", "settings": {}})
        self.assertEqual(result["status"], "ok")
        self.assertIn("ignored 1", result["message"])

    def test_automatic_action_includes_version_and_configuration_without_unrelated_settings(self):
        report = {"applied": 0, "skipped": 0, "failed": 0, "configuration_errors": [], "channels": []}
        settings = {
            "automatic_groups": [{"group": "1", "strategy": "exact", "scope": "countries/canada", "replace": True},
                                 {"group": "9", "strategy": "disabled"}],
            "automatic_prefix": "CA |", "automatic_prefix_mode": "literal",
            "automatic_prefix_rules": [{"group": "1", "mode": "regex", "prefix": "^CA"}],
            "automatic_variant": "standard", "automatic_guide_signals": True,
            "automatic_ignored_channels": ["7", "2"],
            "catalog_filters": [{"mode": "include_contains", "text": "canada"},
                                {"mode": "exclude_regex", "text": "old", "catalog": "tv_logos"}],
            "mappings": [{"channel": "secret-channel", "logo": "secret-logo"}],
            "unrelated_setting": "secret-value",
        }
        options = [{"value": "1", "label": "Canadian locals"}]
        with patch("src.group_options", return_value=options), patch("src.automatic_channels", return_value=[]), \
             patch("src.run_automatic", return_value=report):
            result = Plugin().run("run_automatic", {}, {"data_dir": "/x", "settings": settings})
        self.assertEqual(result["plugin_version"], Plugin.version)
        self.assertEqual(result["configuration"]["snapshot"], "start_of_run")
        self.assertEqual(result["configuration"]["ignored_channels"], [{"number": None, "name": None}, {"number": None, "name": None}])
        groups = result["configuration"]["groups"]
        self.assertEqual(groups[0], {"row": 1, "group": "1", "group_name": "Canadian locals",
                                     "strategy": "exact", "scope": "countries/canada", "replace": True})
        self.assertIsNone(groups[1]["group_name"])
        advanced = result["configuration"]["advanced"]
        self.assertEqual(advanced["prefix_rules"], [{"group": "1", "mode": "regex", "prefix": "^CA"}])
        self.assertEqual(advanced["fuzzy_threshold"], 90)
        self.assertTrue(advanced["guide_id_signals"])
        self.assertEqual(result["configuration"]["catalog_filters"], [
            {"mode": "include_contains", "text": "canada", "catalog": None},
            {"mode": "exclude_regex", "text": "old", "catalog": "tv_logos"},
        ])
        self.assertNotIn("secret", json.dumps(result))

    def test_manual_and_automatic_share_configuration_snapshot(self):
        settings = {"automatic_groups": [{"group": "1", "strategy": "exact"}],
                    "automatic_threshold": 93,
                    "catalog_filters": [{"mode": "include_contains", "text": "us"}],
                    "mappings": [{"channel": "private-channel", "logo": "private-logo"}]}
        auto_report = {"applied": 0, "skipped": 0, "failed": 0, "configuration_errors": [], "channels": []}
        manual_report = {"applied": 1, "skipped": 0, "errors": []}
        with patch("src.group_options", return_value=[{"value": "1", "label": "Locals"}]), \
             patch("src.automatic_channels", return_value=[]), patch("src.run_automatic", return_value=auto_report), \
             patch("src.apply_mappings", return_value=manual_report):
            manual = Plugin().run("apply_changes", {}, {"data_dir": "/x", "settings": settings})
            automatic = Plugin().run("run_automatic", {}, {"data_dir": "/x", "settings": settings})
        self.assertEqual(manual["plugin_version"], Plugin.version)
        self.assertEqual(manual["configuration"], automatic["configuration"])
        self.assertEqual(manual["configuration"]["advanced"]["fuzzy_threshold"], 93)
        self.assertEqual(manual["configuration"]["catalog_filters"][0]["text"], "us")
        self.assertNotIn("private", json.dumps(manual))

    def test_manual_match_continues_if_group_labels_are_unavailable(self):
        report = {"applied": 1, "skipped": 0, "errors": []}
        settings = {"automatic_groups": [{"group": "1", "strategy": "exact"}], "mappings": []}
        with patch("src.group_options", side_effect=RuntimeError("unavailable")), \
             patch("src.apply_mappings", return_value=report), self.assertLogs("src", level="WARNING"):
            result = Plugin().run("apply_changes", {}, {"data_dir": "/x", "settings": settings})
        self.assertEqual(result["applied"], 1)
        self.assertIsNone(result["configuration"]["groups"][0]["group_name"])

    def test_automatic_action_handles_invalid_configuration_snapshot(self):
        report = {"applied": 0, "skipped": 0, "failed": 0, "configuration_errors": ["bad"], "channels": []}
        settings = {"automatic_groups": [{"group": ["invalid"], "strategy": {"secret": "hidden"}}, None],
                    "automatic_prefix_rules": "invalid", "catalog_filters": [None, {"text": {"secret": "hidden"}}]}
        with patch("src.group_options", return_value=[]), patch("src.automatic_channels", return_value=[]), \
             patch("src.run_automatic", return_value=report):
            result = Plugin().run("run_automatic", {}, {"data_dir": "/x", "settings": settings})
        self.assertEqual(result["configuration"]["groups"][0]["strategy"], "<invalid>")
        self.assertEqual(result["configuration"]["groups"][1], {"row": 2, "invalid": True})
        self.assertEqual(result["configuration"]["advanced"]["prefix_rules"], "<invalid>")
        self.assertEqual(result["configuration"]["catalog_filters"], [
            {"invalid": True}, {"mode": None, "text": "<invalid>", "catalog": None},
        ])
        self.assertNotIn("hidden", json.dumps(result))

    def test_unknown_action(self):
        self.assertEqual(Plugin().run("unknown", {}, {})["status"], "error")

    def test_catalog_action_is_routed_to_catalog(self):
        with patch("src.catalogs.tv_logos.update_catalog", return_value=3) as update:
            result = Plugin().run("update_catalog", {}, {"data_dir": "/test", "dispatcharr": {"remove_directory": shutil.rmtree}})
        self.assertEqual(result["status"], "ok")
        self.assertIn("3", result["message"])
        update.assert_called_once_with("/test", remove_directory=shutil.rmtree)

    def test_options_include_multiple_catalog_namespaces(self):
        class Catalog:
            accepts_legacy_paths = False

            def __init__(self, catalog_id):
                self.id = self.label = catalog_id

            def options(self, data_dir):
                return ["same.png"]

        with tempfile.TemporaryDirectory() as root, patch("src.catalogs.CATALOGS", (Catalog("one"), Catalog("two"))):
            fields = make_fields(root, {}, [])
        table = next(field for field in fields if field["id"] == "mappings")
        self.assertEqual([option["value"] for option in table["columns"][1]["options"]],
                         ["one:same.png", "two:same.png"])

    def test_invalid_surrogate_option_does_not_hide_valid_logos(self):
        class Catalog:
            id = "example"
            label = "Example"

            def options(self, data_dir):
                return ["valid.png", "bad-\udcc3.png"]

        with tempfile.TemporaryDirectory() as root, patch("src.catalogs.CATALOGS", (Catalog(),)):
            with self.assertLogs("src.fields", level="WARNING"):
                fields = make_fields(root, {}, [])
        table = next(field for field in fields if field["id"] == "mappings")
        self.assertEqual(table["columns"][1]["options"], [{"value": "example:valid.png", "label": "Example / valid.png"}])


if __name__ == "__main__":
    unittest.main()
