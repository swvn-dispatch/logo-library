import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import Mock

from src.scheduling import action_lock, cron_matches, parse_schedule, run_service, tick


class SchedulingTests(unittest.TestCase):
    def test_validation(self):
        for mode, value in [("interval", "0"), ("interval", "1.5"), ("interval", "87601"),
                            ("cron", "* * *"), ("cron", "60 * * * *"), ("cron", "*/0 * * * *"),
                            ("cron", "* * * * MON"), ("bad", "1")]:
            with self.subTest(mode=mode, value=value), self.assertRaises(ValueError):
                parse_schedule(mode, value)
        self.assertIsNone(parse_schedule("disabled", None))

    def test_cron_utc_and_day_or_weekday(self):
        schedule = parse_schedule("cron", "0 12 1 * 1")
        monday = datetime(2026, 11, 2, 12, tzinfo=timezone.utc).timestamp()
        first = datetime(2026, 11, 1, 12, tzinfo=timezone.utc).timestamp()
        self.assertTrue(cron_matches(schedule, monday))
        self.assertTrue(cron_matches(schedule, first))
        self.assertFalse(cron_matches(schedule, monday + 60))

    def test_interval_independence_restart_and_change(self):
        settings = {"schedule_automatic_mode": "interval", "schedule_automatic_value": "1",
                    "schedule_catalog_mode": "interval", "schedule_catalog_value": "2"}
        dispatch = Mock()
        with tempfile.TemporaryDirectory() as root:
            tick(root, settings, dispatch, 0)
            tick(root, settings, dispatch, 3599)
            dispatch.assert_not_called()
            tick(root, settings, dispatch, 3600)
            tick(root, settings, dispatch, 3600)
            dispatch.assert_called_once_with("run_automatic", {})
            tick(root, settings, dispatch, 7200)
            self.assertEqual(dispatch.call_count, 3)
            settings["schedule_automatic_value"] = "3"
            tick(root, settings, dispatch, 7201)
            self.assertEqual(dispatch.call_count, 3)

    def test_cron_slot_dedup_and_no_catchup(self):
        settings = {"schedule_catalog_mode": "cron", "schedule_catalog_value": "* * * * *"}
        dispatch = Mock()
        with tempfile.TemporaryDirectory() as root:
            tick(root, settings, dispatch, 0)
            tick(root, settings, dispatch, 60)
            tick(root, settings, dispatch, 65)
            tick(root, settings, dispatch, 3600)
            self.assertEqual(dispatch.call_count, 2)
            tick(root, settings, dispatch, 120)
            tick(root, settings, dispatch, 3600)
            self.assertEqual(dispatch.call_count, 2)

    def test_failure_retries_and_invalid_schedule_does_not_block_other(self):
        settings = {"schedule_automatic_mode": "cron", "schedule_automatic_value": "bad",
                    "schedule_catalog_mode": "interval", "schedule_catalog_value": "1"}
        dispatch = Mock(side_effect=[RuntimeError("queue unavailable"), None])
        with tempfile.TemporaryDirectory() as root:
            tick(root, settings, dispatch, 0)
            tick(root, settings, dispatch, 3600)
            tick(root, settings, dispatch, 3610)
        self.assertEqual(dispatch.call_count, 2)

    def test_action_lock_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as root:
            with action_lock(root, "run_automatic") as first:
                with action_lock(root, "run_automatic") as second:
                    with action_lock(root, "update_catalog") as other:
                        self.assertTrue(first)
                        self.assertFalse(second)
                        self.assertTrue(other)

    def test_concurrent_leaders_claim_once(self):
        settings = {"schedule_catalog_mode": "interval", "schedule_catalog_value": "1"}
        dispatch = Mock()
        with tempfile.TemporaryDirectory() as root:
            tick(root, settings, dispatch, 0)
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: tick(root, settings, dispatch, 3600), range(4)))
        dispatch.assert_called_once_with("update_catalog", {})

    def test_service_reads_fresh_settings_and_stops(self):
        settings = {"schedule_catalog_mode": "interval", "schedule_catalog_value": "1"}
        context = {"get_settings": Mock(return_value=settings), "dispatch_scheduled_task": Mock()}
        stop = Mock()
        stop.is_set.side_effect = [False, True]
        with tempfile.TemporaryDirectory() as root:
            context["data_dir"] = root
            run_service(context, stop)
        context["get_settings"].assert_called_once_with()
        stop.wait.assert_called_once_with(10)
