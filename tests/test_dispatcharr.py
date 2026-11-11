from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from src.dispatcharr import assign_logo, automatic_channels, channel_options, group_options, guarded_assign_logo


class DispatcharrTests(unittest.TestCase):
    def test_automatic_channel_snapshot_uses_effective_values(self):
        row = types.SimpleNamespace(id=1, effective_name="Override", effective_channel_group_id=2, effective_logo_id=3)
        models = types.ModuleType("apps.channels.models")
        models.Channel = MagicMock()
        managers = types.ModuleType("apps.channels.managers")
        managers.with_effective_values = MagicMock(return_value=[row])
        with patch.dict(sys.modules, {"apps": types.ModuleType("apps"), "apps.channels": types.ModuleType("apps.channels"),
                                      "apps.channels.models": models, "apps.channels.managers": managers}):
            self.assertEqual(automatic_channels(), [{"id": 1, "name": "Override", "group_id": 2, "logo_id": 3}])

    def test_guard_rechecks_current_settings_and_effective_values(self):
        settings = {"automatic_groups": [{"group": "2", "strategy": "exact", "catalog": "tv_logos"}], "mappings": []}
        expected = {"strategy": "exact", "catalog": "tv_logos", "scope": "", "replace": False,
                    "prefix": "", "prefix_mode": "literal", "variant": "strict", "threshold": 90}
        plugin_model, channel_model, override_model, group_model = (MagicMock() for _ in range(4))
        plugin_model.objects.select_for_update.return_value.filter.return_value.first.return_value = types.SimpleNamespace(settings=settings)
        channel = types.SimpleNamespace(channel_group_id=8, name="Raw", logo_id=None)
        channel_model.objects.select_for_update.return_value.filter.return_value.first.return_value = channel
        override = types.SimpleNamespace(channel_group_id=2, name="Effective", logo_id=None)
        override_model.objects.select_for_update.return_value.filter.return_value.first.return_value = override
        group_model.objects.filter.return_value.exists.return_value = True
        models = types.ModuleType("apps.channels.models")
        models.Channel, models.ChannelOverride, models.ChannelGroup = channel_model, override_model, group_model
        plugin_models = types.ModuleType("apps.plugins.models")
        plugin_models.PluginConfig = plugin_model
        loader = types.ModuleType("apps.plugins.loader")
        loader.normalize_plugin_key = lambda name: name
        db = types.ModuleType("django.db")
        db.transaction = types.SimpleNamespace(atomic=lambda: nullcontext())
        modules = {"django": types.ModuleType("django"), "django.db": db, "apps": types.ModuleType("apps"),
                   "apps.channels": types.ModuleType("apps.channels"), "apps.channels.models": models,
                   "apps.plugins": types.ModuleType("apps.plugins"), "apps.plugins.models": plugin_models,
                   "apps.plugins.loader": loader}
        with patch.dict(sys.modules, modules), patch("src.dispatcharr.assign_logo") as assign:
            args = ("/plugin", "1", "2", "Effective", expected, "tv_logos:a.png", Path("a.png"))
            self.assertIsNone(guarded_assign_logo(*args))
            assign.assert_called_once()
            settings["mappings"] = [{"channel": "1"}]
            self.assertEqual(guarded_assign_logo(*args), "manual_mapping")
            settings["mappings"] = []
            override.logo_id = 5
            self.assertEqual(guarded_assign_logo(*args), "existing_logo")
            override.logo_id = None
            override.name = "Changed"
            self.assertEqual(guarded_assign_logo(*args), "channel_changed")
            override.name = "Effective"
            override.channel_group_id = 3
            self.assertEqual(guarded_assign_logo(*args), "channel_changed")
            override.channel_group_id = 2
            settings["automatic_prefix"] = "US:"
            self.assertEqual(guarded_assign_logo(*args), "settings_changed")
            settings.pop("automatic_prefix")
            settings["automatic_variant"] = "standard"
            self.assertEqual(guarded_assign_logo(*args), "settings_changed")
            settings.pop("automatic_variant")
            settings["automatic_groups"].append(dict(settings["automatic_groups"][0]))
            self.assertEqual(guarded_assign_logo(*args), "settings_changed")
            settings["automatic_groups"].pop()
            settings["automatic_groups"][0]["strategy"] = "disabled"
            self.assertEqual(guarded_assign_logo(*args), "settings_changed")
            group_model.objects.filter.return_value.exists.return_value = False
            self.assertEqual(guarded_assign_logo(*args), "missing_group")
            assign.assert_called_once()

    def test_group_options_use_ids_and_current_names(self):
        group_model = MagicMock()
        group_model.objects.filter.return_value.order_by.return_value = [types.SimpleNamespace(id=7, name="Renamed")]
        models = types.ModuleType("apps.channels.models")
        models.ChannelGroup = group_model
        models.Channel = MagicMock()
        managers = types.ModuleType("apps.channels.managers")
        managers.with_effective_values = MagicMock()
        queryset = managers.with_effective_values.return_value.order_by.return_value
        ids = queryset.values_list.return_value.distinct.return_value
        modules = {"apps": types.ModuleType("apps"), "apps.channels": types.ModuleType("apps.channels"),
                   "apps.channels.models": models, "apps.channels.managers": managers}
        with patch.dict(sys.modules, modules):
            self.assertEqual(group_options(), [{"value": "7", "label": "Renamed"}])
        managers.with_effective_values.return_value.order_by.assert_called_once_with()
        queryset.values_list.assert_called_once_with("effective_channel_group_id", flat=True)
        group_model.objects.filter.assert_called_once_with(pk__in=ids)
        group_model.objects.filter.return_value.order_by.assert_called_once_with("name", "id")

    def test_channel_options_use_effective_number_order(self):
        rows = [types.SimpleNamespace(id=1, effective_name="First", effective_channel_number=2.5),
                types.SimpleNamespace(id=2, effective_name="Second", effective_channel_number=10),
                types.SimpleNamespace(id=3, effective_name="Third", effective_channel_number=None)]
        channel_model = MagicMock()
        queryset = MagicMock()
        queryset.order_by.return_value = rows
        with_effective_values = MagicMock(return_value=queryset)
        expression = MagicMock()
        order = expression.asc.return_value
        models = types.ModuleType("apps.channels.models")
        models.Channel = channel_model
        managers = types.ModuleType("apps.channels.managers")
        managers.with_effective_values = with_effective_values
        django_models = types.ModuleType("django.db.models")
        django_models.F = MagicMock(return_value=expression)
        modules = {"django": types.ModuleType("django"), "django.db": types.ModuleType("django.db"),
                   "django.db.models": django_models, "apps": types.ModuleType("apps"),
                   "apps.channels": types.ModuleType("apps.channels"), "apps.channels.models": models,
                   "apps.channels.managers": managers}
        with patch.dict(sys.modules, modules):
            options = channel_options()
        django_models.F.assert_called_once_with("effective_channel_number")
        expression.asc.assert_called_once_with(nulls_last=True)
        queryset.order_by.assert_called_once_with(order, "effective_name", "id")
        self.assertEqual([option["value"] for option in options], ["1", "2", "3"])
        self.assertEqual(options[0]["label"], "2.5 - First")
        self.assertEqual(options[1]["label"], "10 - Second")
        self.assertEqual(options[2]["label"], "Unnumbered - Third")

    def test_assigns_normal_and_auto_created_channels(self):
        for auto_created in (False, True):
            with self.subTest(auto_created=auto_created), tempfile.TemporaryDirectory() as root:
                channel = MagicMock(auto_created=auto_created)
                channel_model = MagicMock()
                channel_model.objects.select_for_update.return_value.filter.return_value.first.return_value = channel
                logo = object()
                logo_model = MagicMock()
                logo_model.objects.get_or_create.return_value = (logo, True)
                override_model = MagicMock()
                models = types.ModuleType("apps.channels.models")
                models.Channel, models.Logo, models.ChannelOverride = channel_model, logo_model, override_model
                db = types.ModuleType("django.db")
                db.transaction = types.SimpleNamespace(atomic=lambda: nullcontext())
                modules = {"django": types.ModuleType("django"), "django.db": db,
                           "apps": types.ModuleType("apps"), "apps.channels": types.ModuleType("apps.channels"),
                           "apps.channels.models": models}
                source = Path(root) / "source.png"
                source.write_bytes(b"image")
                with patch.dict(sys.modules, modules):
                    assign_logo("12", "countries/a.png", source, Path(root) / "logos")
                destination = Path(logo_model.objects.get_or_create.call_args.kwargs["url"])
                self.assertEqual(destination.read_bytes(), b"image")
                if auto_created:
                    override_model.objects.update_or_create.assert_called_once_with(channel=channel, defaults={"logo": logo})
                    channel.save.assert_not_called()
                else:
                    self.assertIs(channel.logo, logo)
                    channel.save.assert_called_once_with(update_fields=["logo"])
                    override_model.objects.update_or_create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
