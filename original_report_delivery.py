"""One-shot manual report delivery using the PRODUCTION report functions.

Uses the same scan_market(), report.send_scanner_report() and
main.send_portfolio_report() as the scheduled path. Journal rules:
  scanning -> sending -> sent, one identity per explicit request.
  A crash before the first Telegram call leaves 'scanning' (safe to retry).
  A crash after 'sending' is persisted is never resent automatically.
"""
import os, sys, json, hashlib

# Audit-retained claim from the failed 19:59 run (TypeError raised by a bad
# scan_market() call before any Telegram call). Reconciled for this exact
# key only, and only when it still has zero receipts and no failure data.
PROVEN_NOT_SENT = ('original-report:owner-original-report-2026-11-25T19:56:28-Cairo'
                   ':receipt-confirmed-retry')
ATTEMPT = 'original-report:owner-manual-2026-11-26T12:05-Cairo:attempt-1'


def reconcile(journal):
    prior = journal.state.get(PROVEN_NOT_SENT)
    if isinstance(prior, dict) and prior.get('status') == 'claimed' and not prior.get('receipts') and not prior.get('failure'):
        prior.update(status='reconciled-not-sent',
                     reconciliation='Run 45670402389 raised TypeError in scan_market() call before any Telegram call; zero receipts; reconciled by recovery agent')
        journal.persist()


def execute(journal, destination, scan, send_scanner, send_portfolio, bot, track_dates=None):
    journal.load()
    journal.verify_private(destination)
    reconcile(journal)
    journal.assert_no_ambiguous()
    state = journal.state.get(ATTEMPT)
    if state and state.get('status') == 'sent':
        print('Requested report already sent; skipped.'); return 'already-sent'
    if state and state.get('status') == 'sending':
        state['status'] = 'partial'; journal.persist()
        print('Interrupted after sending began; not resending.'); return 'partial-skip'
    if state and state.get('status') == 'partial':
        return 'partial-skip'
    journal.state[ATTEMPT] = {'status': 'scanning', 'receipts': []}; journal.persist()
    receipts = journal.state[ATTEMPT]['receipts']
    original_send = bot.send_message

    def recording_send(chat_id, text, *a, **k):
        message = original_send(chat_id, text, *a, **k)
        receipts.append({'part': len(receipts) + 1, 'message_id': message.message_id,
                         'chat_id': str(message.chat.id), 'date': getattr(message, 'date', None)})
        journal.persist()
        return message

    opportunities = scan()
    journal.state[ATTEMPT]['status'] = 'sending'; journal.persist()
    bot.send_message = recording_send
    try:
        send_scanner(opportunities)
        send_portfolio()
    finally:
        bot.send_message = original_send
    st = journal.state[ATTEMPT]
    st.update(status='sent', parts=len(receipts),
              source_dates=sorted(track_dates) if track_dates else [],
              market_count=len(opportunities or []))
    journal.persist()
    print('Report delivered. Parts', len(receipts), 'Yahoo dates', ','.join(st['source_dates']))
    return 'sent'


def main():
    if '--dry-run' in sys.argv:
        print('No source calls or messages.'); return
    destination = os.environ['ADMIN_CHAT_ID'].strip()
    from private_journal import PrivateJournal
    journal = PrivateJournal(os.environ['TELEGRAM_TOKEN'].strip(), os.environ['GH_TOKEN'], os.environ['GITHUB_REPOSITORY'])
    import scanner, portfolio
    dates = set()
    original = scanner.get_stock_data

    def tracked(symbol, legacy_prices=None):
        result = original(symbol, legacy_prices)
        frame = result[0] if isinstance(result, tuple) else None
        if frame is not None and getattr(frame, 'empty', True) is False:
            dates.add(frame.index[-1].date().isoformat())
        return result
    scanner.get_stock_data = tracked; portfolio.get_stock_data = tracked
    from report import send_scanner_report, bot
    from main import send_portfolio_report
    execute(journal, destination, scanner.scan_market, send_scanner_report, send_portfolio_report, bot, dates)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print('Stopped safely:', type(error).__name__, 'at', getattr(error.__traceback__.tb_next, 'tb_frame', None) and error.__traceback__.tb_next.tb_frame.f_code.co_name, '. No automatic send retry.')
        sys.exit(1)
