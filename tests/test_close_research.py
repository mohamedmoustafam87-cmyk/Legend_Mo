import copy
from datetime import datetime,timedelta
import unittest
from unittest.mock import patch
import config,scanner
from close_research import build_close_research

class CloseResearchTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,24,11,tzinfo=config.TIMEZONE)
        days=[self.now-timedelta(days=230-i) for i in range(231)]
        self.p={'chart':{'result':[{'meta':{'symbol':'COMI.CA','currency':'EGP','exchangeName':'CAI','exchangeTimezoneName':'Africa/Cairo','dataGranularity':'1d','instrumentType':'MUTUALFUND'},'timestamp':[int(d.timestamp()) for d in days],'indicators':{'quote':[{'open':[90.]*231,'high':[101.]*231,'low':[99.]*231,'close':[100.]*231,'volume':[1000.]*231}]}}]}}
    def r(self):return self.p['chart']['result'][0]
    def load(self):return build_close_research(self.p,'COMI.CA',self.now)
    def test_close_only_conflict_is_explicit_not_full_strategy(self):
        df=self.load();self.assertEqual(df.attrs['mode'],'close_research');self.assertEqual(df.attrs['instrument_type'],'MUTUALFUND');self.assertNotIn('Open',df);self.assertNotIn('score',df);self.assertEqual(len(df),230)
    def test_null_gap_retained_in_metadata_not_imputed(self):
        self.r()['indicators']['quote'][0]['close'][-3]=None
        df=self.load();self.assertEqual(len(df),229);self.assertEqual(df.attrs['gap_dates'],['2026-11-22'])
    def test_nonnull_invalid_close_rejected(self):
        self.r()['indicators']['quote'][0]['close'][-3]='broken';self.assertIsNone(self.load())
    def test_wrong_symbol_currency_or_timeframe_rejected(self):
        for key,val in [('symbol','ETEL.CA'),('currency','USD'),('dataGranularity','5m')]:
            old=self.r()['meta'][key];self.r()['meta'][key]=val;self.assertIsNone(self.load());self.r()['meta'][key]=old
    def test_duplicate_timestamp_rejected(self):
        self.r()['timestamp'][-3]=self.r()['timestamp'][-2];self.assertIsNone(self.load())
    def test_not_enabled_for_scanner_by_default(self):
        with patch.object(scanner,'fetch_yahoo_history',return_value=None) as full,patch.object(scanner,'_get_json',side_effect=AssertionError('network')):
            self.assertEqual(scanner.get_stock_data('COMI.CA'),(None,'No Data'));full.assert_called_once()
    def test_ui_opt_in_uses_single_response(self):
        with patch.object(scanner,'_get_json',return_value=self.p) as request,patch.object(scanner,'datetime') as clock:
            clock.now.return_value=self.now;df,source=scanner.get_stock_data('COMI.CA',allow_research=True)
            self.assertEqual(request.call_count,1);self.assertEqual(df.attrs['mode'],'close_research')
    def test_insufficient_indicators_remain_missing(self):
        for key in self.r()['indicators']['quote'][0]:self.r()['indicators']['quote'][0][key]=self.r()['indicators']['quote'][0][key][-10:]
        self.r()['timestamp']=self.r()['timestamp'][-10:]
        df=self.load();self.assertTrue(df[['EMA20','EMA50','MA200','RSI14']].isna().all().all())
