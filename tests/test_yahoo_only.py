import ast
from pathlib import Path
import unittest
from unittest.mock import patch
import scanner


class YahooOnlyTests(unittest.TestCase):
    def test_legacy_secondary_provider_never_fetches(self):
        with patch.object(scanner, '_get_json', side_effect=AssertionError('network')):
            self.assertEqual(scanner.fetch_mubasher_prices(), {})

    def test_intraday_request_cannot_enter_daily_loader(self):
        with patch.object(scanner, '_get_json', side_effect=AssertionError('network')):
            self.assertIsNone(scanner.fetch_yahoo_history('COMI.CA', interval='5m'))

    def test_response_timeframe_must_match(self):
        payload = {'chart': {'result': [{'meta': {'dataGranularity': '5m'}}]}}
        with patch.object(scanner, '_get_json', return_value=payload):
            self.assertIsNone(scanner.fetch_yahoo_history('COMI.CA'))

    def test_ui_quote_loader_does_not_query_other_source(self):
        tree = ast.parse((Path(__file__).parents[1] / 'app.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'load_market_prices')
        fn.decorator_list = []
        ns = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'ui_quote_loader', 'exec'), ns)
        self.assertEqual(ns['load_market_prices'](), {})

class YahooPayloadIntegrityTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timedelta
        import config
        now=datetime(2026,11,24,11,tzinfo=config.TIMEZONE)
        start=now-timedelta(days=310)
        dates=[start+timedelta(days=i) for i in range(310)]
        self.now=now
        self.payload={'chart':{'result':[{'meta':{'dataGranularity':'1d','symbol':'COMI.CA','currency':'EGP','exchangeName':'CAI','exchangeTimezoneName':'Africa/Cairo','instrumentType':'EQUITY'},'timestamp':[int(d.timestamp()) for d in dates],'indicators':{'quote':[{'open':[100.]*310,'high':[101.]*310,'low':[99.]*310,'close':[100.]*310,'volume':[1000.]*310}]}}]}}
    def load(self):
        with patch.object(scanner,'_get_json',return_value=self.payload),patch.object(scanner,'datetime') as clock:
            clock.now.return_value=self.now
            return scanner.fetch_yahoo_history('COMI.CA')
    def test_clean_daily_fixture(self):
        self.assertIsNotNone(self.load())
    def test_duplicate_or_unordered_is_not_silently_fixed(self):
        ts=self.payload['chart']['result'][0]['timestamp']
        ts[-2]=ts[-1]
        self.assertIsNone(self.load())
    def test_null_completed_candle_is_not_dropped(self):
        self.payload['chart']['result'][0]['indicators']['quote'][0]['open'][-2]=None
        self.assertIsNone(self.load())
    def test_misaligned_arrays_rejected(self):
        self.payload['chart']['result'][0]['indicators']['quote'][0]['volume'].pop()
        self.assertIsNone(self.load())
    def test_unfinished_current_session_can_be_removed(self):
        r=self.payload['chart']['result'][0]
        r['timestamp'].append(int(self.now.timestamp()))
        for v in r['indicators']['quote'][0].values():v.append(None)
        self.assertIsNotNone(self.load())
    def test_bad_timestamp_fails_closed(self):
        self.payload['chart']['result'][0]['timestamp'][-1]='bad'
        self.assertIsNone(self.load())
