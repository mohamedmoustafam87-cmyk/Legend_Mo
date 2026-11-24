import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

spec=importlib.util.spec_from_file_location('backtest_review',Path(__file__).parents[1]/'Backtest.py')
backtest=importlib.util.module_from_spec(spec)
spec.loader.exec_module(backtest)

class CacheSafetyTests(unittest.TestCase):
    def test_legacy_cache_needs_provider_revalidation(self):
        import scanner
        with tempfile.TemporaryDirectory() as tmp:
            pd.DataFrame({'Close':[123]}).to_csv(Path(tmp)/'COMI.CA_5y.csv')
            with patch.object(backtest,'CACHE_DIR',tmp),patch.object(scanner,'fetch_yahoo_history',return_value=None) as fetch:
                self.assertEqual(backtest._load_one('COMI.CA','5y'),('COMI.CA',None))
                fetch.assert_called_once_with('COMI.CA',period='5y')
    def test_bad_sidecar_does_not_crash_or_trust_cache(self):
        import scanner
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'COMI.CA_5y.csv';p.write_text('invalid csv')
            Path(str(p)+'.meta.json').write_text('{broken')
            with patch.object(backtest,'CACHE_DIR',tmp),patch.object(scanner,'fetch_yahoo_history',return_value=None) as fetch:
                self.assertEqual(backtest._load_one('COMI.CA','5y'),('COMI.CA',None))
                fetch.assert_called_once()
