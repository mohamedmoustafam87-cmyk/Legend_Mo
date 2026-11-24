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
