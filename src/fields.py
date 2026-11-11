"""Build native Dispatcharr settings fields from the current catalog."""

import logging

from . import catalogs
from .filters import MATCH_TYPES, compile_filters, matches

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
    legacy_catalogs = [catalog.id for catalog in catalogs.CATALOGS if getattr(catalog, "accepts_legacy_paths", False)]
    default_catalog = legacy_catalogs[0] if len(legacy_catalogs) == 1 else None
    rules, filter_errors = compile_filters(settings.get("catalog_filters", []), default_catalog)
    logo_options = []
    all_logos = {}
    for catalog in catalogs.CATALOGS:
        try:
            for path in catalog.options(data_dir):
                value, label = f"{catalog.id}:{path}", f"{catalog.label} / {path}"
                if _valid_text(path) and _valid_text(value) and _valid_text(label):
                    all_logos[value] = label
                    if matches(path, rules.get(catalog.id, [])):
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
                label = all_logos.get(canonical, f"Missing: {logo}")
            except ValueError:
                label = f"Missing: {logo}"
            logo_options.append({"value": logo, "label": label})
    return [
        {"id": "instructions", "type": "info", "label": "Catalog and mappings",
         "description": "After the catalog is downloaded, refreshed, or indexed, click Reload plugin and reopen settings. Dropdowns are not searchable."},
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
        {"id": "catalog_filters_section", "type": "section", "label": "Catalog filters", "collapsed": True},
        {"id": "catalog_filter_instructions", "type": "info", "section": "catalog_filters_section",
         "description": "Filters match full paths without regard to case. Include any matching path, then exclude matches. Save and reload the plugin to update choices. Saved mappings remain available."},
        *([{"id": "catalog_filter_errors", "type": "info", "section": "catalog_filters_section",
            "label": "Ignored filters", "description": " ".join(filter_errors)}] if filter_errors else []),
        {"id": "catalog_filters", "type": "table", "section": "catalog_filters_section", "label": "Filters", "default": [],
         "columns": [
             # Add a catalog select when multiple catalogs are available in the UI.
             {"id": "mode", "label": "Mode", "type": "select", "options": [
                 {"value": f"{operation}_{kind}", "label": f"{operation.title()} {kind.replace('_', ' ')}"}
                 for operation in ("include", "exclude") for kind in MATCH_TYPES
             ]},
             {"id": "text", "label": "Text", "type": "string"},
         ]},
    ]
