"""Non-sending tests that bind to the REAL production function signatures."""
import os, sys, types, inspect, unittest
os.environ.setdefault("TELEGRAM_TOKEN", "123:test"); os.environ.setdefault("ADMIN_CHAT_ID", "123456")
os.environ.setdefault("GH_TOKEN", "x"); os.environ.setdefault("GITHUB_REPOSITORY", "o/r")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, portfolio, report, main as legend_main
import original_report_delivery as ord_


class J:
    def __init__(s, state=None): s.state = state or {}; s.n = 0
    def load(s): pass
    def verify_private(s, d): pass
    def persist(s): s.n += 1
    def assert_no_ambiguous(s):
        if any(isinstance(v, dict) and v.get('status') == 'claimed' for v in s.state.values()): raise ValueError('ambiguous')


class Bot:
    def __init__(s): s.sent = []
    def send_message(s, chat_id, text, parse_mode=None):
        s.sent.append(text)
        return types.SimpleNamespace(message_id=len(s.sent) + 100, chat=types.SimpleNamespace(id=int(chat_id)), date=1)


class T(unittest.TestCase):
    def test_signatures_match_adapter_usage(self):
        self.assertEqual(list(inspect.signature(scanner.scan_market).parameters), [])
        self.assertEqual(list(inspect.signature(portfolio.analyze_user_portfolio).parameters), [])
        self.assertEqual(list(inspect.signature(report.send_scanner_report).parameters), ['opportunities'])
        self.assertEqual(list(inspect.signature(legend_main.send_portfolio_report).parameters), [])
        self.assertEqual(list(inspect.signature(scanner.get_stock_data).parameters), ['symbol', 'legacy_prices'])

    def test_real_senders_with_fake_bot_record_receipts(self):
        bot = Bot(); report.bot = bot; legend_main.bot = bot
        report.ADMIN_CHAT_ID = "123456"; legend_main.ADMIN_CHAT_ID = "123456"
        legend_main.analyze_user_portfolio = lambda: [{'ticker': 'X', 'shares': 1, 'buy_price': 1.0, 'price': 2.0,
            'current_value': 2.0, 'pnl_egp': 1.0, 'pnl_pct': 100.0, 'advice': 'a', 'reason': 'r'}]
        opp = [{'ticker': 'AAA', 'score': 90}]
        j = J({ord_.PROVEN_NOT_SENT: {'status': 'claimed', 'receipts': []}})
        r = ord_.execute(j, "123456", lambda: opp, report.send_scanner_report, legend_main.send_portfolio_report, bot, {'2026-11-25'})
        self.assertEqual(r, 'sent')
        st = j.state[ord_.ATTEMPT]
        self.assertEqual(st['status'], 'sent'); self.assertGreaterEqual(len(st['receipts']), 2)
        self.assertEqual(len(st['receipts']), len(bot.sent))
        self.assertEqual(j.state[ord_.PROVEN_NOT_SENT]['status'], 'reconciled-not-sent')
        self.assertEqual(ord_.execute(j, "123456", lambda: opp, report.send_scanner_report, legend_main.send_portfolio_report, bot), 'already-sent')
        self.assertEqual(len(bot.sent), len(st['receipts']))

    def test_other_claimed_not_reconciled(self):
        j = J({'other': {'status': 'claimed', 'receipts': []}})
        with self.assertRaises(ValueError):
            ord_.execute(j, "1", lambda: [], lambda o: None, lambda: None, Bot())

    def test_scan_failure_leaves_retryable_and_sends_nothing(self):
        bot = Bot(); j = J()
        def boom(): raise RuntimeError('x')
        with self.assertRaises(RuntimeError): ord_.execute(j, "1", boom, lambda o: None, lambda: None, bot)
        self.assertEqual(j.state[ord_.ATTEMPT]['status'], 'scanning'); self.assertEqual(bot.sent, [])

    def test_crash_after_sending_never_resends(self):
        bot = Bot(); j = J()
        def bad(o): raise RuntimeError('tg')
        with self.assertRaises(RuntimeError): ord_.execute(j, "1", lambda: [], bad, lambda: None, bot)
        self.assertEqual(ord_.execute(j, "1", lambda: [], lambda o: bot.send_message("1", "dup"), lambda: None, bot), 'partial-skip')
        self.assertEqual(bot.sent, [])

if __name__ == '__main__': unittest.main()
