"""Build native Dispatcharr settings fields from the current catalog."""

import logging

from . import catalogs

logger = logging.getLogger(__name__)


def _valid_text(value):
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def make_fields(data_dir, settings, channels):
    logo_options = []
    for catalog in catalogs.CATALOGS:
        try:
            for path in catalog.options(data_dir):
                value, label = f"{catalog.id}:{path}", f"{catalog.label} / {path}"
                if _valid_text(path) and _valid_text(value) and _valid_text(label):
                    logo_options.append({"value": value, "label": label})
                else:
                    logger.warning("Skipping invalid logo option from catalog %s", catalog.id)
        except (OSError, ValueError):
            logger.warning("Could not list logos from catalog %s", catalog.id, exc_info=True)
        except Exception:
            logger.exception("Catalog %s failed to list logos", catalog.id)
    channel_options = list(channels)
    channel_ids = {option["value"] for option in channel_options}
    logo_ids = {option["value"] for option in logo_options}
    rows = settings.get("mappings", [])
    if not isinstance(rows, list):
        rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        channel, logo = row.get("channel"), row.get("logo")
        if channel not in (None, "") and str(channel) not in channel_ids:
            channel_ids.add(str(channel))
            channel_options.append({"value": str(channel), "label": f"Missing channel (ID {channel})"})
        if _valid_text(logo) and logo and logo not in logo_ids:
            logo_ids.add(logo)
            try:
                catalog, path = catalogs.parse_logo(logo)
                canonical = f"{catalog.id}:{path}"
                label = f"{catalog.label} / {path}" if canonical in logo_ids else f"Missing: {logo}"
            except ValueError:
                label = f"Missing: {logo}"
            logo_options.append({"value": logo, "label": label})
    return [
        {"id": "instructions", "type": "info", "label": "Catalog and mappings",
         "description": "After the catalog is downloaded or refreshed, click Reload plugin and reopen settings. Dropdowns are not searchable."},
        {"id": "manual_assignment", "type": "section", "label": "Manual assignment", "collapsed": False},
        {"id": "manual_instructions", "type": "info", "section": "manual_assignment",
         "description": "Save mappings before running Apply changes. Removing a mapping does not remove the channel's assigned logo."},
        {"id": "mappings", "type": "table", "section": "manual_assignment", "label": "Channel logo mappings", "default": [],
         "columns": [
             {"id": "channel", "label": "Channel", "type": "select", "options": channel_options},
             {"id": "logo", "label": "Logo path", "type": "select", "options": logo_options},
         ]},
        {"id": "automatic_assignment", "type": "section", "label": "Automatic assignment", "collapsed": False},
        {"id": "automatic_coming_soon", "type": "info", "section": "automatic_assignment",
         "description": "Automatic assignment is coming soon."},
    ]
