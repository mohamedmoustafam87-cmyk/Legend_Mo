from unittest import TestCase
from unittest.mock import patch
import pandas as pd
import test_close_research
from close_research import build_close_research
from daily_research import research_record,format_research
import report,scanner
class FullResearchTests(TestCase):
 def sample(self):
  x=test_close_research.CloseResearchTests();x.setUp();return x
 def test_open_fault_does_not_delete_hlcv(self):
  x=self.sample();df=x.load();r=research_record('COMI.CA',df)
  self.assertEqual(len(df),230);self.assertIsNotNone(r['ATR_14']);self.assertIsNotNone(r['CMF_20']);self.assertIsNone(r['candles']['Hammer']);self.assertTrue(pd.isna(df.iloc[-1]['Upper_Shadow_Pct']));self.assertTrue(r['components']);self.assertIsNotNone(r['levels'])
 def test_engulfing_requires_two_valid_opens(self):
  x=self.sample();x.r()['indicators']['quote'][0]['open'][-2]=99.5
  r=research_record('COMI.CA',x.load());self.assertIsNotNone(r['candles']['Hammer']);self.assertIsNone(r['candles']['Bullish_Engulfing'])
 def test_bad_hlc_not_treated_as_partially_valid_window(self):
  x=self.sample();x.r()['indicators']['quote'][0]['high'][-12]=98
  r=research_record('COMI.CA',x.load());self.assertFalse(r['hlcv_available']);self.assertIsNone(r['ATR_14']);self.assertIsNone(r['levels']);self.assertIsNotNone(r['Close'])
 def test_null_volume_does_not_fabricate_zero(self):
  x=self.sample();x.r()['indicators']['quote'][0]['volume'][-3]=None
  r=research_record('COMI.CA',x.load());self.assertFalse(r['hlcv_available']);self.assertIsNone(r['Volume_Ratio'])
 def test_text_has_all_original_sections_without_personal_claims(self):
  r=research_record('COMI.CA',self.sample().load());text=format_research(r)
  for token in ('الاتجاه والزخم','تدفق الأموال','الدعم والمقاومة','التقييم والأسباب','الدخول والوقف','حجم الصفقة','متابعة المحفظة','2026-11-23'):self.assertIn(token,text)
  self.assertNotIn('100,000',text);self.assertNotIn('437',text);self.assertNotIn('score',r)
 def test_telegram_chunks_fit_utf16_limit_and_retain_sections(self):
  r=research_record('COMI.CA',self.sample().load());msgs=report.format_scanner_messages([],{'close_research':[r,r,r],'n_full_analysis':0})
  self.assertGreater(len(msgs),1)
  for m in msgs:self.assertLessEqual(len(m.encode('utf-16-le'))//2,3800)
  self.assertIn('متابعة المحفظة','\n'.join(msgs))
 def test_clean_equity_still_uses_same_dated_pipeline(self):
  x=self.sample();x.r()['meta']['instrumentType']='EQUITY';x.r()['indicators']['quote'][0]['open']=[100.]*231
  with patch.object(scanner,'_get_json',return_value=x.p),patch.object(scanner,'datetime') as clock:
   clock.now.return_value=x.now;df,_=scanner.get_stock_data('COMI.CA',allow_research=True)
  self.assertEqual(df.attrs['mode'],'close_research');self.assertEqual(df.attrs['history_as_of'],'2026-11-23')

 def test_new_report_is_review_only_without_explicit_execution_gate(self):
  with patch.object(report,'safe_send_message') as send:
   self.assertFalse(report.send_scanner_report([],{'close_research':[{}]}));send.assert_not_called()
