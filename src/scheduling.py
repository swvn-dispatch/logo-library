"""Leader-owned scheduling for plugin actions, with durable slot claims."""

import fcntl
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
TASKS = {"automatic": "run_automatic", "catalog": "update_catalog"}


def _cron_field(text, minimum, maximum):
    values = set()
    for part in text.split(","):
        base, separator, step_text = part.partition("/")
        if separator and (not step_text.isascii() or not step_text.isdigit() or int(step_text) < 1):
            raise ValueError("Invalid cron step")
        step = int(step_text) if separator else 1
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            pieces = base.split("-")
            if len(pieces) != 2 or not all(p.isascii() and p.isdigit() for p in pieces):
                raise ValueError("Invalid cron range")
            start, end = map(int, pieces)
        elif base.isascii() and base.isdigit() and not separator:
            start = end = int(base)
        else:
            raise ValueError("Invalid cron field")
        if start < minimum or end > maximum or start > end:
            raise ValueError("Cron value out of range")
        values.update(range(start, end + 1, step))
    return values


def parse_schedule(mode, value):
    if mode == "disabled":
        return None
    if not isinstance(value, str):
        raise ValueError("Schedule value must be text")
    value = value.strip()
    if mode == "interval":
        if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 87600:
            raise ValueError("Interval must be a whole number of hours from 1 to 87600")
        return int(value) * 3600
    if mode == "cron":
        parts = value.split()
        if len(parts) != 5:
            raise ValueError("Cron requires five fields: minute hour day month weekday")
        fields = [_cron_field(part, *bounds) for part, bounds in zip(
            parts, [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)])]
        if 7 in fields[4]:
            fields[4].add(0)
        return fields, parts[2].startswith("*"), parts[4].startswith("*")
    raise ValueError("Unknown schedule mode")


def cron_matches(schedule, timestamp):
    fields, any_day, any_weekday = schedule
    date = datetime.fromtimestamp(timestamp, timezone.utc)
    day = date.day in fields[2]
    weekday = (date.weekday() + 1) % 7 in fields[4]
    day_matches = (day and weekday) if any_day or any_weekday else (day or weekday)
    return date.minute in fields[0] and date.hour in fields[1] and date.month in fields[3] and day_matches


@contextmanager
def action_lock(data_dir, action):
    """Skip overlapping manual and scheduled executions of the same action."""
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / f"schedule-action-{action}.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _write_state(root, state):
    fd, name = tempfile.mkstemp(prefix=".schedule-", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream)
        os.replace(name, root / "schedule-state.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)


def tick(data_dir, settings, dispatch, now=None):
    """Claim due slots under a shared lock before publishing tasks."""
    now = time.time() if now is None else now
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "schedule-state.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            try:
                state = json.loads((root / "schedule-state.json").read_text(encoding="utf-8"))
                if not isinstance(state, dict):
                    raise ValueError("Invalid state")
            except FileNotFoundError:
                state = {}
            for key, action in TASKS.items():
                mode = settings.get(f"schedule_{key}_mode", "disabled")
                value = settings.get(f"schedule_{key}_value", "")
                try:
                    parsed = parse_schedule(mode, value)
                except ValueError as exc:
                    logger.warning("Invalid %s schedule: %s", key, exc)
                    state.pop(key, None)
                    continue
                if parsed is None:
                    state.pop(key, None)
                    continue
                signature = [mode, value.strip()]
                previous = state.get(key)
                if not isinstance(previous, dict) or previous.get("signature") != signature:
                    state[key] = {"signature": signature, "next": now + parsed if mode == "interval" else int(now // 60)}
                    continue
                if mode == "interval":
                    due = now >= previous["next"]
                    next_value = now + parsed
                else:
                    minute = int(now // 60)
                    due = minute > previous["next"] and cron_matches(parsed, now)
                    next_value = minute
                if due:
                    old = previous["next"]
                    previous["next"] = next_value
                    _write_state(root, state)
                    try:
                        dispatch(action, {})
                    except Exception:
                        previous["next"] = old
                        logger.exception("Failed to dispatch scheduled %s", key)
                elif mode == "cron":
                    previous["next"] = max(previous["next"], next_value)
            _write_state(root, state)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def run_service(context, stop_event):
    while not stop_event.is_set():
        try:
            tick(context["data_dir"], context["get_settings"](), context["dispatch_scheduled_task"])
        except Exception:
            logger.exception("Scheduled task check failed")
        finally:
            try:
                from django.db import close_old_connections
                close_old_connections()
            except ImportError:
                pass
        stop_event.wait(10)
