from unittest import TestCase
import test_close_research
from daily_research import research_record
from portfolio_research import build_portfolio_snapshot
from telegram_presentation import compact_messages,technical_card
class PresentationTests(TestCase):
 def sample(self):
  x=test_close_research.CloseResearchTests();x.setUp();f=x.load();return f,research_record('COMI.CA',f)
 def test_meaning_precedes_acronyms_and_caveats(self):
  f,r=self.sample();text=technical_card(r)
  self.assertLess(text.index('الخلاصة'),text.index('إيه اللي ناقص'))
  self.assertIn('ما يدعم القراءة',text);self.assertIn('ما يضعفها',text);self.assertIn('إيه اللي يغيّر القراءة',text);self.assertNotIn('|',text)
 def test_one_stock_per_technical_card(self):
  f,r=self.sample();msgs=compact_messages([r,dict(r,ticker='ETEL.CA')])
  self.assertIn('COMI.CA',msgs[0]);self.assertNotIn('ETEL.CA',msgs[0]);self.assertIn('ETEL.CA',msgs[1])
 def test_shared_notes_once_and_all_fit(self):
  f,r=self.sample();p=build_portfolio_snapshot({'COMI':{'shares':10,'buy_price':110}},{'COMI':f});msgs=compact_messages([r],p)
  self.assertEqual(''.join(msgs).count('وصف Yahoo للأداة'),1)
  for msg in msgs:self.assertLessEqual(len(msg.encode('utf-16-le'))//2,3800)
  self.assertIn('متوسط شرائك',msgs[0]);self.assertIn('مش هدف فني',''.join(msgs))
 def test_missing_indicators_never_become_bullish(self):
  f,r=self.sample()
  for key in ('EMA20','EMA50','MA200','RSI14','MACD_Hist','CMF_20','ADX_14','Volume_Ratio'):r[key]=None
  text=technical_card(r);self.assertIn('لا تكفي لوصف الاتجاه',text);self.assertNotIn('العام صاعد',text)
