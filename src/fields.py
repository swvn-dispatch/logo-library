"""Build native Dispatcharr settings fields from the current catalog."""

from .catalog import CatalogError, catalog_lock, current_catalog, logo_paths


def make_fields(data_dir, settings, channels):
    try:
        with catalog_lock(data_dir, exclusive=False):
            logos = logo_paths(current_catalog(data_dir))
    except CatalogError:
        logos = []
    channel_options = list(channels)
    logo_options = [{"value": path, "label": path} for path in logos]
    channel_ids = {option["value"] for option in channel_options}
    logo_ids = set(logos)
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
        if isinstance(logo, str) and logo and logo not in logo_ids:
            logo_ids.add(logo)
            logo_options.append({"value": logo, "label": f"Missing: {logo}"})
    return [
        {"id": "instructions", "type": "info", "label": "Catalog and mappings",
         "description": "After the catalog is downloaded or refreshed, click Reload plugin and reopen settings. Save mappings before applying. Dropdowns are not searchable."},
        {"id": "mappings", "type": "table", "label": "Channel logo mappings", "default": [],
         "columns": [
             {"id": "channel", "label": "Channel", "type": "select", "options": channel_options},
             {"id": "logo", "label": "Logo path", "type": "select", "options": logo_options},
         ]},
    ]
