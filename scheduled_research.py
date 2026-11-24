"""Fresh Yahoo dated research for scheduled private reports. No sends or legacy advice."""
from datetime import datetime
from scanner import YAHOO_CHART_URL, HEADERS, REQUEST_TIMEOUT
import requests
from threading import Event
from close_research import build_close_research
from daily_research import research_record
from portfolio import MY_PORTFOLIO
from portfolio_research import build_portfolio_snapshot
from config import EGX_STOCKS, SHARIA_EGX_STOCKS, MAX_REPORT_STOCKS, MAX_WORKERS, TIMEZONE
from concurrent.futures import ThreadPoolExecutor
from telegram_presentation import compact_messages


class SourceThrottled(RuntimeError):
    pass


def screen_records(records, frames):
    """Observed technical conditions, NOT calibrated opportunity/performance ranking."""
    candidates=[]
    for r in records:
        keys=('Close','EMA20','EMA50','MA200','RSI14','MACD_Hist','CMF_20','Volume_Ratio','ADX_14')
        if any(r.get(k) is None for k in keys): continue
        if not (r['Close']>r['EMA20']>r['EMA50'] and r['Close']>r['MA200'] and
                50<=r['RSI14']<=70 and r['MACD_Hist']>0 and r['CMF_20']>0 and
                r['Volume_Ratio']>=1 and r['ADX_14']>=20): continue
        f=frames[r['ticker']]
        if len(f)<20 or 'Volume' not in f:continue
        liquidity=(f.Close*f.Volume).tail(20)
        if liquidity.isna().any():continue
        candidates.append((float(liquidity.mean()),r))
    candidates.sort(key=lambda pair:(-pair[0],pair[1]['ticker']))
    return [r for _,r in candidates[:MAX_REPORT_STOCKS]],len(candidates)


def collect_dated_report(now=None, fetch=None):
    now = now or datetime.now(TIMEZONE)
    stop=Event()
    if fetch is None:
        def fetch(url,params):
            if stop.is_set():raise SourceThrottled()
            response=requests.get(url,params=params,headers=HEADERS,timeout=REQUEST_TIMEOUT)
            if response.status_code in (403,429):
                stop.set();raise SourceThrottled()
            response.raise_for_status()
            return response.json()
    universe = [s for s in EGX_STOCKS if s in set(SHARIA_EGX_STOCKS)]
    symbols = list(dict.fromkeys(universe + [t + '.CA' for t in MY_PORTFOLIO]))
    def load(symbol):
        try:
            payload = fetch(YAHOO_CHART_URL + symbol, params={'range':'2y','interval':'1d'})
            frame = build_close_research(payload, symbol, now)
            return frame if frame is not None and not frame.empty else None
        except SourceThrottled:
            stop.set()
            return None
        except Exception:
            # Never log provider exceptions containing request context or fabricate a quote.
            return None
    with ThreadPoolExecutor(max_workers=max(1,min(MAX_WORKERS,4))) as pool:
        frames = {s:f for s,f in zip(symbols,pool.map(load,symbols)) if f is not None}
    if stop.is_set():raise SourceThrottled('Source throttled; no retry or partial report')
    records = [research_record(s, frames[s]) for s in universe if s in frames]
    if not records:
        raise ValueError('No dated market research available')
    selected, candidate_count = screen_records(records, frames)
    snapshot = build_portfolio_snapshot(MY_PORTFOLIO, frames)
    if not snapshot['valued_count']:
        raise ValueError('No dated portfolio quotes available')
    messages = compact_messages(selected, snapshot)
    header = '\n'.join(['📊 متابعة Yahoo اليومية المؤرخة',
        f'تغطية قائمة الفحص: {len(records)} من {len(universe)} سهم.',
        f'تطابق شروط المتابعة: {candidate_count} سهم، التفصيل حتى {MAX_REPORT_STOCKS} حسب سيولة التداول المرصودة، لا حسب عائد متوقع.',
        'الشروط: السعر فوق متوسط20 و50 و200، ومتوسط20 فوق50؛ قوة نسبية50إلى70؛ زخم وسيولة موجبان؛ حجم لا يقل عن متوسطه؛ قوة اتجاه20فأكثر.',
        'ترتيب السيولة بمتوسط الإغلاق×الحجم لآخر20مشاهدة، وليس ترتيب أفضل استثمار أو احتمال نجاح.',
        'تقرير جديد عند تغير بيانات معروضة فقط. بيانات يوم سابق، مش متابعة لحظية.'])
    messages.insert(0, header)
    from telegram_presentation import common_notes
    if not selected: messages.append(common_notes(records))
    return {'messages': messages, 'records': selected, 'snapshot': snapshot,
            'coverage_dates':{r['ticker']:r['history_as_of'] for r in records}}
