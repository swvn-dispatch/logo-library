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
