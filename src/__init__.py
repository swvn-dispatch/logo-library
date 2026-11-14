"""Dispatcharr entry point for Logo Library."""

import json
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .dispatcharr import (assign_logo, automatic_channels, channel_options, dispatcharr_version,
                          group_options, guarded_assign_logo, ignore_latest_skipped, map_latest_skipped, store_skipped_ids)
from .automatic_run import run_automatic
from .automatic import configuration_snapshot
from .fields import make_fields
from .filters import filter_snapshot
from .mappings import apply_mappings, manual_configuration_snapshot
from . import catalogs
from .scheduling import action_lock, run_service

_MANIFEST = json.loads((Path(__file__).parent / "plugin.json").read_text(encoding="utf-8"))
logger = logging.getLogger(__name__)


def _channel_sort_key(item):
    try:
        number = Decimal(str(item.get("channel")))
        if not number.is_finite():
            raise InvalidOperation
        return (0, number, str(item.get("name", "")).casefold())
    except (InvalidOperation, ValueError):
        return (1, Decimal(0), str(item.get("name", "")).casefold())


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
        if "start_service" in context:
            context["start_service"](lambda stop: run_service(context, stop), name="scheduled-tasks")
        else:
            logger.warning("Scheduled tasks unavailable: Dispatcharr does not provide start_service")

    def run(self, action, params, context):
        if action in {"run_automatic", "update_catalog"} and context.get("data_dir"):
            with action_lock(context["data_dir"], action) as acquired:
                if not acquired:
                    result = {"status": "error", "message": "This task is already running."}
                else:
                    result = self._run(action, params, context)
        else:
            result = self._run(action, params, context)
        return {**result, "plugin_version": self.version, "dispatcharr_version": dispatcharr_version()}

    def _run(self, action, params, context):
        def assign(channel, identity, image):
            logo_dir = context["dispatcharr"]["ensure_directory"]("logos")
            return assign_logo(channel, identity, image, logo_dir)

        if action == "ignore_skipped":
            return ignore_latest_skipped(context["code_dir"])
        if action == "map_skipped":
            return map_latest_skipped(context["code_dir"])
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
            grouped = {"success": [], "skipped": [], "failed": []}
            for item in result["channels"]:
                grouped[item["status"] if item["status"] in {"skipped", "failed"} else "success"].append(item)
            for entries in grouped.values():
                entries.sort(key=_channel_sort_key)
            result["channels"] = grouped
            result["channel_numbers"] = True
            if reference:
                result["ignored_channel_reference"] = reference
            return {"status": status, "message": message,
                    "configuration": configuration, **result}
        if action == "apply_changes":
            settings = context.get("settings", {})
            try:
                channels = automatic_channels()
            except Exception:
                logger.warning("Could not retrieve channel numbers for Manual Match results", exc_info=True)
                channels = []
            configuration = manual_configuration_snapshot(settings.get("mappings", []), channels)
            configuration["catalog_filters"] = filter_snapshot(settings.get("catalog_filters", []))
            result = apply_mappings(context["data_dir"], settings.get("mappings", []), assign)
            status = "partial" if result["skipped"] else "ok"
            channel_by_id = {str(channel["id"]): channel for channel in channels}
            for error in result["errors"]:
                channel = channel_by_id.get(str(error["channel"]), {})
                error["channel"] = channel.get("number")
                error["name"] = channel.get("name")
            message = f"Applied {result['applied']}, ignored {result.get('ignored', 0)}, skipped {result['skipped']}."
            return {"status": status, "message": message,
                    "configuration": configuration, **result}
        result = catalogs.run_action(action, params, context)
        return result if result is not None else {"status": "error", "message": f"Unknown action: {action}"}
