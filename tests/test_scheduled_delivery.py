import copy
import os
import unittest
from datetime import datetime
from unittest.mock import patch
from config import TIMEZONE
import scheduled_delivery as delivery


def clock(day=24,hour=10,minute=30):
    return datetime(2026,11,day,hour,minute,tzinfo=TIMEZONE)


def report(text='sample',date='2026-11-23'):
    return {'messages':[text,'second part'],
            'records':[{'ticker':'COMI.CA','history_as_of':date}],
            'snapshot':{'rows':[{'ticker':'ETEL','date':date}]}}


class Journal:
    def __init__(self):
        self.state={};self.calls=[];self.writes=[];self.failure=False;self.fail_persist=None
    def load(self): self.calls.append('load')
    def assert_no_ambiguous(self):
        if any(v.get('status')=='claimed' for v in self.state.values()): raise ValueError('ambiguous')
    def persist(self):
        self.writes.append(copy.deepcopy(self.state))
        if self.fail_persist is not None and len(self.writes)==self.fail_persist: raise TimeoutError()
    def verify_private(self,destination): self.calls.append('verify')
    def telegram(self,method,body):
        self.calls.append(method)
        self.assert_claim()
        if self.failure: raise TimeoutError()
        return {'ok':True,'result':{'chat':{'id':12345},'message_id':len(self.calls),'date':1}}
    def assert_claim(self):
        assert any(v.get('status')=='claimed' for v in self.writes[-1].values())


class ScheduledTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_CHAT_ID':'12345'});self.env.start()
        self.addCleanup(self.env.stop)
        self.j=Journal()
    def run_delivery(self,text='sample',date='2026-11-23',now=None,**kw):
        return delivery.execute(now=now or clock(),enabled=True,journal=self.j,
            collect=lambda **_:report(text,date),**kw)
    def baseline(self): self.assertEqual(self.run_delivery(),'baseline-only')
    def test_gate_has_no_io(self):
        with patch('scheduled_research.collect_dated_report') as collect:
            self.assertEqual(delivery.execute(enabled=False,journal=self.j),'gated')
            self.assertEqual(delivery.execute(enabled=True,dry_run=True,journal=self.j),'gated')
            self.assertFalse(self.j.calls);collect.assert_not_called()
    def test_original_slots_and_delayed_catchup(self):
        self.assertIsNone(delivery.due_slot(clock(hour=10,minute=29)))
        self.assertTrue(delivery.due_slot(clock(hour=10,minute=51)).endswith('10:30'))
        self.assertTrue(delivery.due_slot(clock(hour=12,minute=55)).endswith('12:30'))
        self.assertTrue(delivery.due_slot(clock(hour=14,minute=49)).endswith('14:30'))
        self.assertTrue(delivery.due_slot(clock(hour=15,minute=50)).endswith('15:00'))
        self.assertIsNone(delivery.due_slot(clock(day=20)))
        self.assertIsNone(delivery.due_slot(clock(day=21)))
    def test_aware_time_required(self):
        with self.assertRaises(ValueError):delivery.due_slot(datetime(2026,11,24))
    def test_bootstrap_is_silent(self):
        self.baseline();self.assertNotIn('sendMessage',self.j.calls)
    def test_same_slot_never_refetches(self):
        self.baseline()
        self.assertEqual(self.run_delivery(text='new'),'slot-already-checked')
        self.assertNotIn('sendMessage',self.j.calls)
    def test_unchanged_next_slot_and_day_skip(self):
        self.baseline()
        self.assertEqual(self.run_delivery(now=clock(hour=12,minute=45)),'unchanged')
        self.assertEqual(self.run_delivery(now=clock(day=25)),'unchanged')
        self.assertNotIn('sendMessage',self.j.calls)
    def test_new_session_sends_once_and_records_receipts(self):
        self.baseline()
        self.assertEqual(self.run_delivery(text='new',date='2026-11-24',now=clock(day=25)),'sent')
        self.assertEqual(self.j.calls.count('sendMessage'),2)
        sent=[v for v in self.j.state.values() if v.get('status')=='sent'][0]
        self.assertEqual(len(sent['receipts']),2)
        self.assertEqual(self.run_delivery(text='new',date='2026-11-24',now=clock(day=25,hour=12,minute=31)),'unchanged')
    def test_timeout_blocks_later_all_sends(self):
        self.baseline();self.j.failure=True
        with self.assertRaises(TimeoutError): self.run_delivery(text='new',now=clock(hour=12,minute=31))
        self.j.failure=False
        with self.assertRaises(ValueError): self.run_delivery(text='newer',now=clock(day=25))
        self.assertEqual(self.j.calls.count('sendMessage'),1)
    def test_old_manual_ambiguous_claim_blocks(self):
        self.j.state['old-part']={'status':'claimed'}
        with self.assertRaises(ValueError): self.run_delivery()
        self.assertNotIn('verify',self.j.calls)
    def test_persist_failure_before_claim_never_sends(self):
        self.baseline();self.j.fail_persist=len(self.j.writes)+2
        with self.assertRaises(TimeoutError):self.run_delivery(text='new',now=clock(hour=12,minute=31))
        self.assertNotIn('sendMessage',self.j.calls)
    def test_regressed_source_not_sent(self):
        self.baseline()
        self.assertEqual(self.run_delivery(text='older',date='2026-11-22',now=clock(hour=12,minute=31)),'source-regressed')
        self.assertNotIn('sendMessage',self.j.calls)
    def test_missing_previously_priced_symbol_not_sent(self):
        self.baseline()
        missing=report('missing');missing['snapshot']['rows']=[]
        self.assertEqual(delivery.execute(now=clock(hour=12,minute=31),enabled=True,journal=self.j,collect=lambda **_:missing),'source-regressed')
        self.assertNotIn('sendMessage',self.j.calls)
    def test_changed_destination_blocks_before_scan(self):
        self.baseline()
        with patch.dict(os.environ,{'ADMIN_CHAT_ID':'67890'}):
            with self.assertRaises(ValueError):self.run_delivery(now=clock(hour=12,minute=31))
        self.assertNotIn('sendMessage',self.j.calls)
    def test_date_and_cost_visible_changes_identity(self):
        a=report();b=report();b['messages'][0]='changed cost'
        self.assertNotEqual(delivery.content_identity(a),delivery.content_identity(b))
    def test_oversized_message_rejected(self):
        with self.assertRaises(ValueError):delivery.content_identity(report('x'*3801))


class ResearchIntegrationTests(unittest.TestCase):
    def test_supplied_yahoo_fetch_once_per_symbol_no_legacy(self):
        import scheduled_research as r
        import pandas as pd
        frame=pd.DataFrame({'Close':[100.]})
        record={'ticker':'COMI.CA','history_as_of':'2026-11-23'}
        snapshot={'valued_count':1}
        calls=[]
        def fetch(url,params):calls.append(url);return {'sample':True}
        with patch.object(r,'EGX_STOCKS',['COMI.CA','ETEL.CA']),patch.object(r,'SHARIA_EGX_STOCKS',['COMI.CA']),patch.object(r,'MY_PORTFOLIO',{'COMI':{},'ETEL':{}}),patch.object(r,'build_close_research',return_value=frame),patch.object(r,'research_record',return_value=record),patch.object(r,'build_portfolio_snapshot',return_value=snapshot) as build,patch.object(r,'compact_messages',return_value=['body']),patch.object(r,'screen_records',return_value=([record],1)):
            result=r.collect_dated_report(now=clock(),fetch=fetch)
        self.assertEqual(len(calls),2)
        self.assertEqual(set(build.call_args.args[1]),{'COMI.CA','ETEL.CA'})
        self.assertEqual(len(result['messages']),2)
    def test_no_research_fails_closed(self):
        import scheduled_research as r
        with patch.object(r,'build_close_research',return_value=None):
            with self.assertRaises(ValueError):r.collect_dated_report(now=clock(),fetch=lambda *a,**k:{})


class ScreenTests(unittest.TestCase):
    def test_rule_screen_orders_liquidity_not_arbitrary_list(self):
        import scheduled_research as r
        import pandas as pd
        def rec(ticker,volume=1):
            return dict(ticker=ticker,Close=110,EMA20=108,EMA50=105,MA200=100,
                RSI14=60,MACD_Hist=1,CMF_20=.1,Volume_Ratio=volume,ADX_14=25)
        records=[rec('LOW.CA'),rec('NO.CA',.5),rec('HIGH.CA')]
        frames={t:pd.DataFrame({'Close':[110.]*20,'Volume':[v]*20}) for t,v in [('LOW.CA',100),('NO.CA',500),('HIGH.CA',1000)]}
        selected,count=r.screen_records(records,frames)
        self.assertEqual([x['ticker'] for x in selected],['HIGH.CA','LOW.CA'])
        self.assertEqual(count,2)
        records[0]['RSI14']=None
        self.assertEqual(len(r.screen_records(records,frames)[0]),1)
    def test_public_request_is_no_session_and_stops_on_throttle(self):
        import scheduled_research as r
        response=type('Response',(),{'status_code':429})()
        with patch.object(r,'EGX_STOCKS',['COMI.CA']),patch.object(r,'SHARIA_EGX_STOCKS',['COMI.CA']),patch.object(r,'MY_PORTFOLIO',{}),patch.object(r.requests,'get',return_value=response) as get:
            with self.assertRaises(r.SourceThrottled):r.collect_dated_report(now=clock())
        self.assertEqual(get.call_count,1)
        self.assertNotIn('cookies',get.call_args.kwargs)
        self.assertNotIn('auth',get.call_args.kwargs)
    def test_throttle_persists_pause_and_never_repolls(self):
        import scheduled_research as r
        journal=Journal()
        with patch.dict(os.environ,{'ADMIN_CHAT_ID':'12345'}):
            with self.assertRaises(r.SourceThrottled):
                delivery.execute(now=clock(),enabled=True,journal=journal,collect=lambda **_:(_ for _ in ()).throw(r.SourceThrottled()))
            with self.assertRaises(ValueError):
                delivery.execute(now=clock(hour=12,minute=31),enabled=True,journal=journal,collect=lambda **_:self.fail('source repoll'))
        self.assertTrue(journal.state['_scheduled_v1']['source_paused'])
