from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from src.dispatcharr import assign_logo


class DispatcharrTests(unittest.TestCase):
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
