"""Non-sending tests for scheduled_delivery: slot gating and durable dedup.

No network, no Telegram, no market data: clock, journal and send functions
are all fakes/injected. Run: python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import datetime

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("ADMIN_CHAT_ID", "123456")
os.environ.setdefault("GH_TOKEN", "test-gh")
os.environ.setdefault("GITHUB_REPOSITORY", "owner/repo")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TIMEZONE  # noqa: E402
import scheduled_delivery as sd  # noqa: E402


def at(day, h, m):
    return datetime.fromisoformat(f"{day}T{h:02d}:{m:02d}:00").replace(tzinfo=TIMEZONE)


# 2026-11-25 is a Wednesday, 2026-11-26 Thursday, 2026-11-27 Friday,
# 2026-11-29 Sunday (all within the same EGX week).
class DueSlotTests(unittest.TestCase):
    def test_before_first_slot(self):
        self.assertIsNone(sd.due_slot(at("2026-11-26", 10, 29)))

    def test_exact_slot_start(self):
        self.assertEqual(sd.due_slot(at("2026-11-26", 10, 30)), "2026-11-26T10:30")

    def test_delayed_trigger_still_finds_slot(self):
        # A GitHub runner 25 minutes late still delivers the 10:30 slot.
        self.assertEqual(sd.due_slot(at("2026-11-26", 10, 55)), "2026-11-26T10:30")

    def test_slot_expires_at_next_slot(self):
        self.assertEqual(sd.due_slot(at("2026-11-26", 12, 30)), "2026-11-26T12:30")

    def test_last_slot_bounded(self):
        self.assertEqual(sd.due_slot(at("2026-11-26", 15, 45)), "2026-11-26T15:00")
        self.assertIsNone(sd.due_slot(at("2026-11-26", 16, 0)))

    def test_friday_not_trading(self):
        self.assertIsNone(sd.due_slot(at("2026-11-27", 10, 30)))

    def test_sunday_trading(self):
        self.assertEqual(sd.due_slot(at("2026-11-29", 10, 30)), "2026-11-29T10:30")

    def test_holiday_skipped(self):
        import config
        config.EGX_HOLIDAYS.add("2026-11-26")
        try:
            self.assertIsNone(sd.due_slot(at("2026-11-26", 10, 30)))
        finally:
            config.EGX_HOLIDAYS.discard("2026-11-26")

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            sd.due_slot(datetime(2026, 11, 26, 10, 30))


class FakeJournal:
    def __init__(self):
        self.state = {}
        self.persist_count = 0

    def load(self):
        pass

    def assert_no_ambiguous(self):
        pass

    def verify_private(self, destination):
        pass

    def persist(self):
        self.persist_count += 1


class ExecuteTests(unittest.TestCase):
    def setUp(self):
        self.journal = FakeJournal()
        self.calls = []

    def _run(self, now, scan_result=("opp",), fail_scan=False,
             fail_scanner=False, fail_portfolio=False):
        def scan():
            self.calls.append("scan")
            if fail_scan:
                raise RuntimeError("source down")
            return scan_result

        def send_scanner(opps):
            self.calls.append("scanner")
            if fail_scanner:
                raise RuntimeError("telegram error")

        def send_portfolio():
            self.calls.append("portfolio")
            if fail_portfolio:
                raise RuntimeError("telegram error")

        return sd.execute(now=now, journal=self.journal, scan=scan,
                          send_scanner=send_scanner, send_portfolio=send_portfolio)

    def test_happy_path_sends_once(self):
        self.assertEqual(self._run(at("2026-11-26", 10, 35)), "sent")
        self.assertEqual(self.calls, ["scan", "scanner", "portfolio"])
        state = self.journal.state["_scheduled_v2"]
        self.assertEqual(state["slots"]["2026-11-26T10:30"], "sent")
        self.assertEqual(state["receipts"]["2026-11-26T10:30"], ["scanner", "portfolio"])
        # Next tick of the same slot sends nothing.
        self.assertEqual(self._run(at("2026-11-26", 10, 45)), "slot-already-sent")
        self.assertEqual(self.calls, ["scan", "scanner", "portfolio"])

    def test_crash_during_scan_allows_retry(self):
        with self.assertRaises(RuntimeError):
            self._run(at("2026-11-26", 10, 35), fail_scan=True)
        state = self.journal.state["_scheduled_v2"]["slots"]
        self.assertEqual(state["2026-11-26T10:30"], "scanning")
        # Retry on a later tick completes the slot.
        self.assertEqual(self._run(at("2026-11-26", 10, 50)), "sent")
        self.assertEqual(self.calls.count("scanner"), 1)

    def test_crash_while_sending_never_resends(self):
        with self.assertRaises(RuntimeError):
            self._run(at("2026-11-26", 10, 35), fail_portfolio=True)
        state = self.journal.state["_scheduled_v2"]["slots"]
        self.assertEqual(state["2026-11-26T10:30"], "sending")
        # Later ticks mark the slot partial and do not resend anything.
        self.assertEqual(self._run(at("2026-11-26", 10, 50)), "partial-skip")
        self.assertEqual(state["2026-11-26T10:30"], "partial")
        self.assertEqual(self.calls.count("scanner"), 1)
        self.assertEqual(self._run(at("2026-11-26", 11, 0)), "slot-already-partial")
        self.assertEqual(self.calls.count("scan"), 1)

    def test_no_slot_no_calls(self):
        self.assertEqual(self._run(at("2026-11-26", 9, 0)), "not-due")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.journal.persist_count, 0)

    def test_dry_run_no_io(self):
        self.assertEqual(sd.execute(now=at("2026-11-26", 10, 35), dry_run=True), "dry-run")
        self.assertEqual(self.calls, [])

    def test_destination_change_blocks(self):
        self.journal.state["_scheduled_v2"] = {
            "slots": {}, "receipts": {}, "destination_hash": "different"}
        with self.assertRaises(ValueError):
            self._run(at("2026-11-26", 10, 35))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
