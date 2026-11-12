"""Dispatcharr channel and logo integration."""

import hashlib
import os
from pathlib import Path
import shutil
import tempfile

LOGO_DIR = Path("/data/logos")


def assign_logo(channel_id, relative, image, logo_dir=LOGO_DIR):
    """Copy a catalog image into Dispatcharr storage and assign it to a channel."""
    from django.db import transaction
    from apps.channels.models import Channel, ChannelOverride, Logo

    try:
        channel_pk = int(channel_id)
        if channel_pk <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Invalid channel ID") from None

    logo_dir = Path(logo_dir)
    logo_dir.mkdir(parents=True, exist_ok=True)
    # Prefix prevents collisions with uploads and the path hash supports shared logos.
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()
    extension = image.suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise ValueError("Unsupported logo image format")
    destination = logo_dir / f"logo-library-{digest}{extension}"
    with transaction.atomic():
        channel = Channel.objects.select_for_update().filter(pk=channel_pk).first()
        if channel is None:
            raise ValueError(f"Channel {channel_id} no longer exists")
        fd, temp_name = tempfile.mkstemp(prefix=".logo-library-", suffix=".tmp", dir=logo_dir)
        try:
            with os.fdopen(fd, "wb") as output, image.open("rb") as source:
                shutil.copyfileobj(source, output)
            os.replace(temp_name, destination)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        logo, _ = Logo.objects.get_or_create(url=str(destination), defaults={"name": relative})
        if channel.auto_created:
            ChannelOverride.objects.update_or_create(channel=channel, defaults={"logo": logo})
        else:
            channel.logo = logo
            channel.save(update_fields=["logo"])


def get_plugin_state(code_dir):
    """Find loader-owned persistent storage and saved mappings for this install."""
    from apps.plugins.loader import normalize_plugin_key
    from apps.plugins.models import PluginConfig
    from apps.plugins.sandbox import stable_plugin_data_path

    key = normalize_plugin_key(Path(code_dir).name)
    config = PluginConfig.objects.filter(key=key).first()
    storage_key = (config.slug or config.key) if config else key
    path = stable_plugin_data_path(key, str(code_dir), storage_key)
    settings = (config.settings or {}) if config else {}
    return path, settings


def channel_options():
    from django.db.models import F
    from apps.channels.managers import with_effective_values
    from apps.channels.models import Channel

    channels = with_effective_values(Channel.objects.all()).order_by(
        F("effective_channel_number").asc(nulls_last=True), "effective_name", "id"
    )
    return [
        {"value": str(channel.id), "label": f"{channel.effective_channel_number:.1f}".removesuffix(".0") + f" - {channel.effective_name}"
         if channel.effective_channel_number is not None else f"Unnumbered - {channel.effective_name}"}
        for channel in channels
    ]


def group_options():
    """List groups used by channels after applying group overrides."""
    from apps.channels.managers import with_effective_values
    from apps.channels.models import Channel, ChannelGroup

    group_ids = with_effective_values(Channel.objects.all()).order_by().values_list("effective_channel_group_id", flat=True).distinct()
    return [{"value": str(group.id), "label": group.name}
            for group in ChannelGroup.objects.filter(pk__in=group_ids).order_by("name", "id")]


def automatic_channels():
    """Take an effective-value snapshot for an explicitly requested run."""
    from apps.channels.managers import with_effective_values
    from apps.channels.models import Channel

    return [{"id": channel.id, "name": channel.effective_name,
             "group_id": channel.effective_channel_group_id, "logo_id": channel.effective_logo_id,
             "guide_id": channel.effective_tvg_id}
            for channel in with_effective_values(Channel.objects.all())]


def guarded_assign_logo(code_dir, channel_id, group_id, name, guide_id, expected, identity, image):
    """Recheck saved settings and effective values in the assignment transaction."""
    from django.db import transaction
    from apps.channels.models import Channel, ChannelGroup, ChannelOverride
    from apps.plugins.loader import normalize_plugin_key
    from apps.plugins.models import PluginConfig
    from . import catalogs
    from .automatic import compile_groups
    from .mappings import manual_disposition

    with transaction.atomic():
        key = normalize_plugin_key(Path(code_dir).name)
        plugin = PluginConfig.objects.select_for_update().filter(key=key).first()
        if plugin is None or not isinstance(plugin.settings, dict):
            return "settings_changed"
        settings = plugin.settings
        mappings = settings.get("mappings", [])
        if not isinstance(mappings, list):
            return "settings_changed"
        channel_rows = [row for row in mappings if isinstance(row, dict) and str(row.get("channel")) == channel_id]
        disposition = manual_disposition(channel_rows)
        if disposition:
            return disposition
        if not ChannelGroup.objects.filter(pk=group_id).exists():
            return "missing_group"
        groups, _ = compile_groups(settings.get("automatic_groups", []), [group_id],
                                   {catalog.id for catalog in catalogs.CATALOGS}, settings)
        if groups.get(group_id) != expected:
            return "settings_changed"
        channel = Channel.objects.select_for_update().filter(pk=channel_id).first()
        if channel is None:
            return "missing_channel"
        override = ChannelOverride.objects.select_for_update().filter(channel_id=channel_id).first()

        def effective(field):
            override_value = getattr(override, field, None)
            return override_value if override_value is not None else getattr(channel, field)

        if str(effective("channel_group_id")) != group_id or effective("name") != name:
            return "channel_changed"
        if expected["guide_signals"] and effective("tvg_id") != guide_id:
            return "channel_changed"
        if effective("logo_id") is not None and not expected["replace"]:
            return "existing_logo"
        assign_logo(channel_id, identity, image)
        return None
