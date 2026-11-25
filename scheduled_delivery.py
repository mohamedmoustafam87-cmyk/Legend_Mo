"""Scheduled report delivery: Cairo-clock slots, bounded catchup, durable dedup.

Reactivated Nov 25 2026 on the user's explicit approval (WhatsApp) after the
Nov 24 automatic-send pause. Slots come from config.REPORT_TIMES (Cairo local).

GitHub Actions schedules have no guaranteed precision: a run can arrive late
or not at all. This script therefore decides from the Cairo clock itself
instead of trusting trigger timing, and records every slot durably in the
encrypted PrivateJournal (delivery-state branch) so repeated triggers,
retries and runner crashes can never send the same slot twice.

Lateness policy: a slot is due from its clock time until the next slot's
clock time (the last slot until LATEST_SLOT_END). A slot passed entirely is
skipped rather than sent stale. Delivery guarantee is at-most-once per slot:
a runner crash or a dropped schedule can skip a slot, never duplicate it.
"""

import hashlib
import os
import sys
from datetime import datetime

from config import TIMEZONE, REPORT_TIMES, TRADING_WEEKDAYS, EGX_HOLIDAYS

# Last slot (15:00) stays due this long; cron ticks stop at 15:50 Cairo.
LATEST_SLOT_END = (16, 0)

CONTROL_KEY = "_scheduled_v2"


def due_slot(now):
    """Return the slot key currently due (YYYY-MM-DDTHH:MM), or None.

    Trading weekdays only (Sun-Thu) and not an EGX holiday. The latest
    REPORT_TIMES slot whose clock time has passed is due until the next
    slot's clock time; before the first slot or after LATEST_SLOT_END
    nothing is due.
    """
    if now.tzinfo is None:
        raise ValueError("Aware datetime required")
    now = now.astimezone(TIMEZONE)
    if now.weekday() not in TRADING_WEEKDAYS:
        return None
    if now.date().isoformat() in EGX_HOLIDAYS:
        return None
    slots = sorted(REPORT_TIMES)
    bounds = slots[1:] + [LATEST_SLOT_END]
    for (h, m), end in zip(slots, bounds):
        if (h, m) <= (now.hour, now.minute) < end:
            return f"{now.date().isoformat()}T{h:02d}:{m:02d}"
    return None


def execute(now=None, dry_run=False, journal=None,
            scan=None, send_scanner=None, send_portfolio=None):
    """Run one scheduled tick. Returns a short status string.

    State machine per slot, persisted BEFORE the work it names:
      scanning  - set before any market-data call; a crash here means no
                  Telegram message was attempted, so a later tick retries.
      sending   - set after the scan, before the first Telegram call; a
                  crash here is ambiguous (a message may have gone out),
                  so a later tick marks the slot 'partial' and does NOT
                  resend anything.
      sent      - both report parts completed; later ticks skip.
      partial   - interrupted after 'sending'; later ticks skip.
    """
    now = now or datetime.now(TIMEZONE)
    slot = due_slot(now)
    if dry_run:
        print(f"dry-run: now={now.astimezone(TIMEZONE).isoformat()} slot={slot}")
        return "dry-run"
    if slot is None:
        print("No configured slot due; no source calls.")
        return "not-due"

    if journal is None:
        from private_journal import PrivateJournal
        journal = PrivateJournal(os.environ["TELEGRAM_TOKEN"].strip(),
                                 os.environ["GH_TOKEN"].strip(),
                                 os.environ["GITHUB_REPOSITORY"])
    journal.load()
    journal.assert_no_ambiguous()
    control = journal.state.setdefault(CONTROL_KEY, {"slots": {}, "receipts": {}})

    destination = os.environ["ADMIN_CHAT_ID"].strip()
    destination_hash = hashlib.sha256(destination.encode()).hexdigest()
    if control.get("destination_hash") not in (None, destination_hash):
        raise ValueError("Destination changed; no automatic disclosure")
    control["destination_hash"] = destination_hash

    state = control["slots"].get(slot)
    if state in ("sent", "partial"):
        return f"slot-already-{state}"
    if state == "sending":
        # A previous run was interrupted after Telegram calls may have
        # started. Never resend; record and skip.
        control["slots"][slot] = "partial"
        journal.persist()
        return "partial-skip"

    if scan is None:
        from scanner import scan_market
        scan = scan_market
    if send_scanner is None:
        from report import send_scanner_report
        send_scanner = send_scanner_report
    if send_portfolio is None:
        from main import send_portfolio_report
        send_portfolio = send_portfolio_report

    if state != "scanning":
        control["slots"][slot] = "scanning"
        journal.persist()
    opportunities = scan()

    control["slots"][slot] = "sending"
    journal.persist()

    journal.verify_private(destination)
    send_scanner(opportunities)
    control["receipts"][slot] = ["scanner"]
    journal.persist()
    send_portfolio()
    control["receipts"][slot].append("portfolio")
    control["slots"][slot] = "sent"
    journal.persist()
    print(f"Scheduled slot {slot} delivered once.")
    return "sent"


if __name__ == "__main__":
    try:
        execute(dry_run="--dry-run" in sys.argv)
    except Exception as error:
        # Never expose request URLs, credentials, holdings or report body.
        print("Stopped safely:", type(error).__name__, ". No automatic send retry.")
        sys.exit(1)
