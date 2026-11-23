import ast
import importlib
import os
from pathlib import Path
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
import report
import config


class ScheduleTests(unittest.TestCase):
    def dt(self, value):
        return datetime.fromisoformat(value).replace(tzinfo=config.TIMEZONE)

    def test_report_window(self):
        for value in ['2026-11-23T10:30:00', '2026-11-23T10:34:59',
                      '2026-07-05T15:00:00']:
            self.assertTrue(main.is_scheduled_report_time(self.dt(value)))
        for value in ['2026-11-23T10:29:59', '2026-11-23T10:35:00',
                      '2026-11-23T11:00:00']:
            self.assertFalse(main.is_scheduled_report_time(self.dt(value)))

    def test_trading_days(self):
        self.assertTrue(main.is_trading_day(self.dt('2026-11-22T10:30:00')))
        self.assertFalse(main.is_trading_day(self.dt('2026-11-20T10:30:00')))
        self.assertFalse(main.is_trading_day(self.dt('2026-11-21T10:30:00')))

    def test_manual_mode(self):
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'schedule'}):
            self.assertFalse(main.is_manual_trigger())
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'workflow_dispatch'}):
            self.assertTrue(main.is_manual_trigger())

    def test_dry_run_never_scans_or_sends(self):
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'workflow_dispatch'}), \
             patch.object(sys, 'argv', ['main.py', '--dry-run']), \
             patch.object(main, 'scan_market') as scan, \
             patch.object(main, 'safe_send_message') as send, \
             patch.object(main, 'require_telegram') as check:
            main.main()
            scan.assert_not_called()
            send.assert_not_called()
            check.assert_not_called()

    def test_outside_window_never_sends(self):
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'schedule'}), \
             patch.object(main, 'is_trading_day', return_value=True), \
             patch.object(main, 'is_scheduled_report_time', return_value=False), \
             patch.object(main, 'safe_send_message') as send:
            main.main()
            send.assert_not_called()


class ReportTests(unittest.TestCase):
    def test_scanner_success(self):
        with patch.object(report, 'format_scanner_messages', return_value=['a','b']), \
             patch.object(report, 'safe_send_message', return_value=True) as send:
            self.assertTrue(report.send_scanner_report([], {}))
            self.assertEqual(send.call_count, 2)

    def test_scanner_partial_failure_is_false(self):
        with patch.object(report, 'format_scanner_messages', return_value=['a','b']), \
             patch.object(report, 'safe_send_message', side_effect=[False,True]) as send:
            self.assertFalse(report.send_scanner_report([], {}))
            self.assertEqual(send.call_count, 2)

    def test_empty_portfolio_is_skipped_successfully(self):
        with patch.object(report, 'safe_send_message') as send:
            self.assertTrue(report.send_portfolio_report([]))
            send.assert_not_called()

    def test_portfolio_success_and_failure(self):
        for success in (True, False):
            with patch.object(report, 'format_portfolio_messages', return_value=['a']), \
                 patch.object(report, 'safe_send_message', return_value=success):
                self.assertEqual(report.send_portfolio_report([{}]), success)

    def test_plain_text_fallback(self):
        from unittest.mock import Mock
        bot = Mock()
        bot.send_message.side_effect = [ValueError('format'), None]
        with patch.object(report, 'get_bot', return_value=bot):
            self.assertTrue(report.safe_send_message('mock-destination', '*test*'))
            self.assertEqual(bot.send_message.call_count, 2)

    def test_send_failure(self):
        from unittest.mock import Mock
        bot = Mock()
        bot.send_message.side_effect = ValueError('mock-failure')
        with patch.object(report, 'get_bot', return_value=bot):
            self.assertFalse(report.safe_send_message('mock-destination', 'test'))

    def test_credentials_are_environment_reads(self):
        tree = ast.parse((ROOT / 'config.py').read_text())
        assignments = {node.targets[0].id: node.value for node in tree.body
                       if isinstance(node, ast.Assign)
                       and isinstance(node.targets[0], ast.Name)}
        for key in ['TELEGRAM_TOKEN', 'ADMIN_CHAT_ID']:
            self.assertIsInstance(assignments[key], ast.Call)
        with patch.dict(os.environ, {'TELEGRAM_TOKEN': '', 'ADMIN_CHAT_ID': ''}):
            importlib.reload(config)
            with self.assertRaises(ValueError):
                config.require_telegram()
        importlib.reload(config)


if __name__ == '__main__':
    unittest.main()

