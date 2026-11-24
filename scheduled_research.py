"""Fresh Yahoo dated research for scheduled private reports. No sends or legacy advice."""
from datetime import datetime
from scanner import _get_json, YAHOO_CHART_URL
from close_research import build_close_research
from daily_research import research_record
from portfolio import MY_PORTFOLIO
from portfolio_research import build_portfolio_snapshot
from config import EGX_STOCKS, SHARIA_EGX_STOCKS, MAX_REPORT_STOCKS, MAX_WORKERS, TIMEZONE
from concurrent.futures import ThreadPoolExecutor
from telegram_presentation import compact_messages


def collect_dated_report(now=None, fetch=None):
    now = now or datetime.now(TIMEZONE)
    fetch = fetch or _get_json
    universe = [s for s in EGX_STOCKS if s in set(SHARIA_EGX_STOCKS)]
    symbols = list(dict.fromkeys(universe + [t + '.CA' for t in MY_PORTFOLIO]))
    def load(symbol):
        try:
            payload = fetch(YAHOO_CHART_URL + symbol, params={'range':'2y','interval':'1d'})
            frame = build_close_research(payload, symbol, now)
            return frame if frame is not None and not frame.empty else None
        except Exception:
            # Never log provider exceptions containing request context or fabricate a quote.
            return None
    with ThreadPoolExecutor(max_workers=max(1,min(MAX_WORKERS,4))) as pool:
        frames = {s:f for s,f in zip(symbols,pool.map(load,symbols)) if f is not None}
    records = [research_record(s, frames[s]) for s in universe if s in frames]
    if not records:
        raise ValueError('No dated market research available')
    # Stable configured order, explicitly not a recommendation ranking.
    selected = records[:MAX_REPORT_STOCKS]
    snapshot = build_portfolio_snapshot(MY_PORTFOLIO, frames)
    if not snapshot['valued_count']:
        raise ValueError('No dated portfolio quotes available')
    messages = compact_messages(selected, snapshot)
    header = '\n'.join(['📊 متابعة Yahoo اليومية المؤرخة',
        f'تغطية قائمة الفحص: {len(records)} من {len(universe)} سهم.',
        f'التفصيل لأول {len(selected)} أسهم متاحة بترتيب القائمة، مش ترتيب أفضل فرص.',
        'تقرير جديد عند تغير بيانات معروضة فقط. بيانات يوم سابق، مش متابعة لحظية.'])
    messages.insert(0, header)
    return {'messages': messages, 'records': selected, 'snapshot': snapshot}
