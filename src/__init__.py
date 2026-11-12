"""Dispatcharr entry point for Logo Library."""

import json
import logging
from pathlib import Path

from .dispatcharr import (assign_logo, automatic_channels, channel_options,
                          group_options, guarded_assign_logo, ignore_latest_skipped, store_skipped_ids)
from .automatic_run import run_automatic
from .automatic import configuration_snapshot
from .fields import make_fields
from .mappings import apply_mappings
from . import catalogs

_MANIFEST = json.loads((Path(__file__).parent / "plugin.json").read_text(encoding="utf-8"))
logger = logging.getLogger(__name__)


class Plugin:
    name = _MANIFEST["name"]
    version = _MANIFEST["version"]
    description = _MANIFEST["description"]
    author = _MANIFEST["author"]
    help_url = _MANIFEST["help_url"]
    actions = _MANIFEST["actions"]

    def get_fields(self, context):
        return make_fields(context["data_dir"], context["settings"], channel_options(), group_options())

    def on_leader_acquired(self, context):
        for catalog in catalogs.CATALOGS:
            catalog.on_leader_acquired(context)

    def run(self, action, params, context):
        def assign(channel, identity, image):
            logo_dir = context["dispatcharr"]["ensure_directory"]("logos")
            return assign_logo(channel, identity, image, logo_dir)

        if action == "ignore_skipped":
            return ignore_latest_skipped(context["code_dir"])
        if action == "run_automatic":
            options = group_options()
            groups = [option["value"] for option in options]
            settings = context.get("settings", {})
            channels = automatic_channels()
            configuration = configuration_snapshot(settings, options, channels)
            result = run_automatic(context["data_dir"], settings, channels,
                                   groups, catalogs.CATALOGS,
                                   lambda *args: guarded_assign_logo(context["code_dir"], *args, assign=assign))
            status = "partial" if result["skipped"] or result["failed"] or result["configuration_errors"] else "ok"
            message = (f"Applied {result['applied']}, manual mappings preserved {result.get('preserved', 0)}, "
                       f"ignored {result.get('ignored', 0)}, skipped {result['skipped']}, failed {result['failed']}.")
            generic_count = sum(item.get("method") == "network_fallback" and item["status"] == "applied"
                                for item in result["channels"])
            if generic_count:
                message += f" Generic network logos applied: {generic_count}."
            skipped_ids = [item["channel"] for item in result["channels"] if item["status"] in {"skipped", "failed"}]
            reference = store_skipped_ids(context["code_dir"], skipped_ids) if skipped_ids else None
            numbers = {str(channel["id"]): channel.get("number") for channel in channels}
            for item in result["channels"]:
                item["channel"] = numbers.get(str(item["channel"]))
            result["channel_numbers"] = True
            if reference:
                result["ignored_channel_reference"] = reference
            return {"status": status, "message": message, "plugin_version": self.version,
                    "configuration": configuration, **result}
        if action == "apply_changes":
            settings = context.get("settings", {})
            try:
                options = group_options()
            except Exception:
                logger.warning("Could not retrieve group labels for Manual Match results", exc_info=True)
                options = []
            try:
                channels = automatic_channels()
            except Exception:
                logger.warning("Could not retrieve channel numbers for Manual Match results", exc_info=True)
                channels = []
            configuration = configuration_snapshot(settings, options, channels)
            result = apply_mappings(context["data_dir"], settings.get("mappings", []), assign)
            status = "partial" if result["skipped"] else "ok"
            channel_by_id = {str(channel["id"]): channel for channel in channels}
            for error in result["errors"]:
                channel = channel_by_id.get(str(error["channel"]), {})
                error["channel"] = channel.get("number")
                error["name"] = channel.get("name")
            message = f"Applied {result['applied']}, ignored {result.get('ignored', 0)}, skipped {result['skipped']}."
            return {"status": status, "message": message, "plugin_version": self.version,
                    "configuration": configuration, **result}
        result = catalogs.run_action(action, params, context)
        return result if result is not None else {"status": "error", "message": f"Unknown action: {action}"}
