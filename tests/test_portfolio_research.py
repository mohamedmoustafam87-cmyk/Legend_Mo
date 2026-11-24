from unittest import TestCase
from unittest.mock import patch
from decimal import Decimal
import test_close_research
from portfolio_research import build_portfolio_snapshot,format_private_portfolio
from portfolio import prepare_dated_portfolio,MY_PORTFOLIO
class DatedPortfolioTests(TestCase):
 def frame(self):
  x=test_close_research.CloseResearchTests();x.setUp();return x.load()
 def test_math_uses_selected_quantities_and_cost_not_defaults(self):
  p=build_portfolio_snapshot({'ETEL':{'shares':79,'buy_price':141.133}},{'ETEL':self.frame()});r=p['rows'][0]
  self.assertEqual(Decimal(r['cost']),Decimal('11149.507'));self.assertEqual(Decimal(r['value']),Decimal('7900'));self.assertEqual(Decimal(r['pnl']),Decimal('-3249.507'));self.assertTrue(p['complete'])
 def test_missing_symbol_stays_and_total_not_claimed(self):
  p=build_portfolio_snapshot({'A':{'shares':1,'buy_price':100},'B':{'shares':2,'buy_price':50}},{'A':self.frame()})
  self.assertEqual(p['count'],2);self.assertFalse(p['complete']);self.assertIsNone(p['rows'][1]['close']);self.assertEqual(Decimal(p['covered_value']),100);self.assertIn('ليس إجمالي المحفظة',''.join(format_private_portfolio(p)))
 def test_mixed_dates_not_summed_as_snapshot(self):
  a=self.frame();b=self.frame();b.attrs['history_as_of']='2026-11-22'
  p=build_portfolio_snapshot({'A':{'shares':1,'buy_price':100},'B':{'shares':2,'buy_price':50}},{'A':a,'B':b})
  self.assertIsNone(p['covered_value']);self.assertFalse(p['complete'])
 def test_all_selected_holdings_preserved_without_network(self):
  with patch('portfolio.get_stock_data',side_effect=AssertionError('no network')):
   p=prepare_dated_portfolio({})
  self.assertEqual(len(p['rows']),len(MY_PORTFOLIO));self.assertEqual(p['valued_count'],0)
 def test_bad_holdings_not_silently_zeroed(self):
  for count in (0,-1,True,1.5):
   with self.assertRaises(ValueError):build_portfolio_snapshot({'A':{'shares':count,'buy_price':10}}, {})
 def test_private_blocks_fit_and_no_personal_trade_directive(self):
  p=prepare_dated_portfolio({'ETEL':self.frame()});messages=format_private_portfolio(p)
  for message in messages:self.assertLessEqual(len(message.encode('utf-16-le'))//2,3800)
  text=''.join(messages);self.assertNotIn('خروج / تخفيف',text);self.assertIn('79',text);self.assertIn('141.133',text)
