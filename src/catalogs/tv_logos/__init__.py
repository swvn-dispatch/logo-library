"""tv-logo/tv-logos catalog."""

from contextlib import contextmanager

from .catalog import catalog_lock, current_catalog, logo_paths, resolve_logo, update_catalog


class TvLogosCatalog:
    id = "tv_logos"
    label = "TV Logos"
    accepts_legacy_paths = True
    actions = [{
        "id": "update_catalog",
        "label": "Refresh TV Logos library",
        "description": "Download the latest tv-logos catalog. Reload the plugin afterward.",
        "button_label": "Refresh TV Logos library",
        "button_color": "teal",
        "async": True,
    }]

    def on_leader_acquired(self, context):
        if current_catalog(context["data_dir"]) is None:
            context["dispatch_task"]("update_catalog", {"initial": True})

    def run(self, action, params, context):
        if action != "update_catalog":
            raise ValueError(f"Unknown catalog action: {action}")
        count = update_catalog(context["data_dir"], only_if_missing=bool(params.get("initial")))
        if count is None:
            return {"status": "ok", "message": "TV Logos catalog already exists."}
        return {"status": "ok", "message": f"Downloaded {count} TV Logos images. Reload the plugin before editing mappings."}

    def options(self, data_dir):
        with catalog_lock(data_dir, exclusive=False):
            return logo_paths(current_catalog(data_dir))

    @contextmanager
    def resolve(self, data_dir, path):
        with catalog_lock(data_dir, exclusive=False):
            snapshot = current_catalog(data_dir)
            if snapshot is None:
                raise ValueError("Catalog has not been downloaded")
            yield resolve_logo(snapshot, path)
