from unittest import TestCase
from unittest.mock import patch
from datetime import datetime
import scanner,report,config
import test_close_research

class ResearchPipelineTests(TestCase):
    def payload(self):
        x=test_close_research.CloseResearchTests();x.setUp();return x.p,x.now
    def test_full_scan_keeps_research_separate_and_formats_dated_prices(self):
        p,now=self.payload()
        with patch.object(scanner,'_get_json',return_value=p),patch.object(scanner,'datetime') as clock,patch.object(scanner,'EGX_STOCKS',['COMI.CA']),patch.object(scanner,'SHARIA_EGX_STOCKS',['COMI.CA']),patch.object(scanner,'load_model_stats',return_value=None),patch.object(scanner,'evaluate_stock_strategy',side_effect=AssertionError('research entered strategy')),patch.object(report,'safe_send_message',side_effect=AssertionError('must not send')):
            clock.now.return_value=now
            top,ctx=scanner.scan_market(return_context=True)
            messages=report.format_scanner_messages(top,ctx)
        self.assertEqual(top,[]);self.assertEqual(len(ctx['close_research']),1);self.assertEqual(ctx['n_full_analysis'],0)
        text='\n'.join(messages);self.assertIn('2026-11-23',text);self.assertIn('100.00',text);self.assertIn('RSI14',text);self.assertNotIn('لا توجد إشارات مطابقة',text);self.assertNotIn('احتمالية',text)
    def test_delay_alone_keeps_clean_history_with_date(self):
        p,now=self.payload();r=p['chart']['result'][0];r['meta']['instrumentType']='EQUITY';q=r['indicators']['quote'][0];q['open']=[100.]*len(q['open'])
        # Remove the most recent completed session, representing honestly delayed data.
        r['timestamp']=r['timestamp'][:-2]
        for k in q:q[k]=q[k][:-2]
        with patch.object(scanner,'datetime') as clock:
            clock.now.return_value=now;df=scanner.validate_yahoo_history(p,'COMI.CA')
        self.assertIsNotNone(df);self.assertTrue(df.attrs['session_delay_warning']);self.assertEqual(df.attrs['history_as_of'],'2026-11-22')
    def test_zero_usable_data_does_not_fake_report(self):
        with patch.object(scanner,'load_universe_frames',return_value={}):
            with self.assertRaises(RuntimeError):scanner.scan_market(return_context=True)
