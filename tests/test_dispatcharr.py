from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from src.dispatcharr import assign_logo, channel_options


class DispatcharrTests(unittest.TestCase):
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
        self.assertEqual(options[1]["label"], "10.0 - Second")
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
