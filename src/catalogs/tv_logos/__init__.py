"""tv-logo/tv-logos catalog."""

from contextlib import contextmanager

from .catalog import (
    catalog_lock, current_catalog, ensure_index, read_index, release_initialization,
    reserve_initialization, resolve_logo, update_catalog,
)


class TvLogosCatalog:
    id = "tv_logos"
    label = "TV Logos"
    accepts_legacy_paths = True
    actions = [{
        "id": "update_catalog",
        "label": "Refresh tv-logos downloaded catalog",
        "description": "Download the latest tv-logos catalog.",
        "button_label": "Refresh",
        "button_color": "teal",
        "async": True,
    }]

    def on_leader_acquired(self, context):
        data_dir = context["data_dir"]
        if read_index(current_catalog(data_dir)) is not None:
            return
        token = reserve_initialization(data_dir)
        if token is None:
            return
        try:
            context["dispatch_task"]("update_catalog", {"initial": True, "request_token": token})
        except Exception:
            release_initialization(data_dir, token)
            raise

    def run(self, action, params, context):
        if action != "update_catalog":
            raise ValueError(f"Unknown catalog action: {action}")
        data_dir = context["data_dir"]
        try:
            if params.get("initial"):
                if current_catalog(data_dir) is None:
                    update_catalog(data_dir, only_if_missing=True, remove_directory=context["dispatcharr"]["remove_directory"])
                count = ensure_index(data_dir)
                if count is None:
                    raise ValueError("TV Logos catalog is unavailable")
                return {"status": "ok", "message": f"TV Logos library ready with {count} images. Reload the plugin before editing mappings."}
            count = update_catalog(data_dir, remove_directory=context["dispatcharr"]["remove_directory"])
            return {"status": "ok", "message": f"Downloaded {count} TV Logos images. Reload the plugin before editing mappings."}
        finally:
            release_initialization(data_dir, params.get("request_token"))

    def options(self, data_dir):
        return read_index(current_catalog(data_dir)) or []

    @contextmanager
    def resolve(self, data_dir, path):
        with catalog_lock(data_dir, exclusive=False):
            snapshot = current_catalog(data_dir)
            if snapshot is None:
                raise ValueError("Catalog has not been downloaded")
            yield resolve_logo(snapshot, path)
