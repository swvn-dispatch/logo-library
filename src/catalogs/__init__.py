"""Logo catalog registry and catalog-qualified identities.

Catalogs expose id, label, accepts_legacy_paths, actions, options(data_dir),
resolve(data_dir, path), on_leader_acquired(context), and run(action, params,
context). resolve is a context manager that keeps the logo usable until exit.
Providers may expose a matching adapter for catalog-specific path conventions;
catalogs without one use conservative generic defaults from catalogs.matching.
Dispatcharr v2 requires every catalog action to also appear in plugin.json.
"""

from .tv_logos import TvLogosCatalog

CATALOGS = (TvLogosCatalog(),)


def find_catalog(catalog_id):
    return next((catalog for catalog in CATALOGS if catalog.id == catalog_id), None)


def parse_logo(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Select a logo")
    catalog_id, separator, path = value.partition(":")
    if separator:
        catalog = find_catalog(catalog_id)
        if catalog is None or not path:
            raise ValueError(f"Unknown logo catalog: {catalog_id}")
        return catalog, path
    legacy = [catalog for catalog in CATALOGS if catalog.accepts_legacy_paths]
    if len(legacy) != 1:
        raise ValueError("Cannot resolve legacy logo path")
    return legacy[0], value


def catalog_actions():
    return [action for catalog in CATALOGS for action in catalog.actions]


def run_action(action, params, context):
    matches = [catalog for catalog in CATALOGS if action in {item["id"] for item in catalog.actions}]
    if len(matches) > 1:
        raise ValueError(f"Duplicate catalog action: {action}")
    return matches[0].run(action, params, context) if matches else None
