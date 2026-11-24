import ast
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from datetime import datetime
import numpy as np
import pandas as pd
import scanner
import config

class DataSafetyTests(unittest.TestCase):
    def frame(self):
        dates=pd.date_range('2025-01-01',periods=300,freq='D')
        c=np.linspace(100,120,300)
        return pd.DataFrame({'Open':c,'High':c+1,'Low':c-1,'Close':c,'Volume':10000},index=dates)
    def test_valid_bars(self):
        self.assertTrue(scanner.data_quality_ok(self.frame()))
    def test_inconsistent_ohlc_rejected(self):
        for key,value in [('Open',999),('High',1),('Low',999),('Volume',-1),('Close',float('inf'))]:
            df=self.frame();df.iloc[-1,df.columns.get_loc(key)]=value
            self.assertFalse(scanner.data_quality_ok(df),key)
    def test_metadata_is_not_guessed(self):
        m={'symbol':'COMI.CA','currency':'EGP','exchangeName':'CAI','exchangeTimezoneName':'Africa/Cairo','instrumentType':'EQUITY'}
        self.assertTrue(scanner.history_metadata_ok(m,'COMI.CA'))
        for key,value in [('currency','USD'),('symbol','WRONG.CA'),('instrumentType','MUTUALFUND'),('exchangeName','NYQ')]:
            self.assertFalse(scanner.history_metadata_ok(dict(m,**{key:value}),'COMI.CA'))
    def test_asof_calendar(self):
        for now,expected in [('2026-11-24T11:00:00','2026-11-23'),('2026-11-21T16:00:00','2026-11-19'),('2026-11-24T16:00:00','2026-11-24')]:
            self.assertEqual(scanner.latest_expected_session(datetime.fromisoformat(now).replace(tzinfo=config.TIMEZONE)).isoformat(),expected)
    def test_unverified_current_price_not_promoted(self):
        with patch.object(scanner,'fetch_yahoo_history',return_value=self.frame()):
            df,_=scanner.get_stock_data('COMI.CA',{'COMI':999})
        self.assertEqual(df.attrs['current_price'],120)
        self.assertFalse(df.attrs['is_realtime'])
    def test_total_data_failure_is_not_no_opportunities(self):
        with patch.object(scanner,'fetch_mubasher_prices',return_value={}),patch.object(scanner,'load_universe_frames',return_value={}):
            with self.assertRaises(RuntimeError):scanner.scan_market()
    def test_strategy_failure_is_not_fake_neutral_score(self):
        # Evaluate the loader alone, without starting the web UI or network.
        tree=ast.parse((Path(__file__).parents[1]/'app.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_analysis')
        fn.decorator_list=[]
        ns={'pd':pd,'np':np,'get_stock_data':lambda *x:(self.frame(),'test'),
            'calculate_indicators':lambda x:x,'attach_context':lambda x,c:x,
            'evaluate_stock_strategy':lambda *x:None,'safe_float':lambda x,*d:float(x)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'loader','exec'),ns)
        self.assertEqual(ns['load_analysis']('COMI.CA',{},None),(None,None))
if __name__=='__main__':unittest.main()

class ContextSafetyTests(unittest.TestCase):
    def test_context_date_must_match(self):
        from signals import attach_context
        df=pd.DataFrame({'Return_60D':[2.]},index=pd.to_datetime(['2026-11-23']))
        out=attach_context(df,{'date':'2026-11-20','breadth50':70,'rs_quantiles':list(range(101))})
        self.assertTrue(pd.isna(out['Breadth_50'].iloc[-1]))
    def test_bad_model_does_not_leave_cached_model(self):
        import tempfile,ml
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'model.json';p.write_text('{bad json')
            ml._CACHE.update(path='previous',mtime=1,stats={'old':True},model=object())
            self.assertIsNone(ml.load_model_stats(str(p)))
            self.assertIsNone(ml._CACHE['model'])
