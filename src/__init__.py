"""Dispatcharr entry point for Logo Library."""

import json
from pathlib import Path

from .dispatcharr import assign_logo, channel_options, get_plugin_state, group_options
from .fields import make_fields
from .mappings import apply_mappings
from . import catalogs

_MANIFEST = json.loads((Path(__file__).parent / "plugin.json").read_text(encoding="utf-8"))


class Plugin:
    name = _MANIFEST["name"]
    version = _MANIFEST["version"]
    description = _MANIFEST["description"]
    author = _MANIFEST["author"]
    help_url = _MANIFEST["help_url"]
    actions = _MANIFEST["actions"]

    @property
    def fields(self):
        data_dir, settings = get_plugin_state(Path(__file__).parent)
        return make_fields(data_dir, settings, channel_options(), group_options())

    def on_leader_acquired(self, context):
        for catalog in catalogs.CATALOGS:
            catalog.on_leader_acquired(context)

    def run(self, action, params, context):
        if action == "apply_changes":
            result = apply_mappings(context["data_dir"], context.get("settings", {}).get("mappings", []), assign_logo)
            status = "partial" if result["skipped"] else "ok"
            errors = "; ".join(f"row {e['row']} (channel {e['channel']}): {e['message']}" for e in result["errors"])
            message = f"Applied {result['applied']}, skipped {result['skipped']}."
            if errors:
                message += " " + errors
            return {"status": status, "message": message, **result}
        result = catalogs.run_action(action, params, context)
        return result if result is not None else {"status": "error", "message": f"Unknown action: {action}"}
