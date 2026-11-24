"""UI-only dated close research. Never a strategy input or trade recommendation."""
import numpy as np
import pandas as pd


def build_close_research(payload, symbol, now):
    try:
        from config import TIMEZONE_NAME
        r=payload['chart']['result'][0];m=r['meta'];ts=r['timestamp'];q=r['indicators']['quote'][0]
        if not (m.get('symbol')==symbol and m.get('currency')=='EGP'
                and m.get('exchangeName') in ('CAI','EGX')
                and m.get('exchangeTimezoneName')==TIMEZONE_NAME and m.get('dataGranularity')=='1d'):
            return None
        if not isinstance(ts,list) or not ts or any(isinstance(t,bool) or not isinstance(t,(int,float)) or not np.isfinite(t) for t in ts):return None
        if any(b<=a for a,b in zip(ts,ts[1:])):return None
        if any(not isinstance(q.get(k),list) or len(q[k])!=len(ts) for k in ('open','high','low','close','volume')):return None
        dates=pd.to_datetime(ts,unit='s',utc=True).tz_convert(TIMEZONE_NAME).tz_localize(None).normalize()
        if dates.has_duplicates or dates[-1].date()>now.date():return None
        # Always exclude today's potentially unfinished session in this historical-only mode.
        past=dates.date<now.date();dates=dates[past]
        close=pd.to_numeric(pd.Series(q['close']),errors='coerce')[past].to_numpy(dtype=float)
        missing=np.isnan(close)
        # Null provider rows are reported, not invented. Non-null malformed values reject.
        raw=np.array(q['close'],dtype=object)[past]
        if any(v is not None for v in raw[missing]):return None
        if any(isinstance(v,bool) for v in raw):return None
        if any(not np.isfinite(v) or v<=0 for v in close[~missing]):return None
        good=pd.DataFrame({'Close':close},index=dates)
        gaps=[d.date().isoformat() for d in dates[missing]]
        good=good.loc[~missing].copy()
        if len(good)<2:return None
        good['EMA20']=good.Close.ewm(span=20,adjust=False,min_periods=20).mean()
        good['EMA50']=good.Close.ewm(span=50,adjust=False,min_periods=50).mean()
        good['MA200']=good.Close.rolling(200,min_periods=200).mean()
        delta=good.Close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
        rsi=100-100/(1+gain/loss.replace(0,np.nan))
        rsi=rsi.mask((loss==0)&(gain>0),100).mask((gain==0)&(loss>0),0)
        good['RSI14']=rsi
        # Validate Open only for the SAME selected latest historical row. Never
        # backtrack to a different date or manufacture Open from previous Close.
        latest_date=good.index[-1]
        source_index=list(pd.to_datetime(ts,unit='s',utc=True).tz_convert(TIMEZONE_NAME).tz_localize(None).normalize()).index(latest_date)
        bar=[q[k][source_index] for k in ('open','high','low','close')]
        valid_bar=all(isinstance(v,(int,float)) and not isinstance(v,bool) and np.isfinite(v) and v>0 for v in bar)
        if valid_bar:
            o,h,l,c=bar;epsilon=abs(c)*1e-6
            valid_bar=h+epsilon>=max(o,c,l) and l-epsilon<=min(o,c,h)
        good.attrs['selected_open']=float(bar[0]) if valid_bar else None
        good.attrs['selected_bar_ohlc_consistent']=bool(valid_bar)
        good.attrs.update(mode='close_research',history_as_of=good.index[-1].date().isoformat(),
                          gap_dates=gaps,instrument_type=str(m.get('instrumentType','unknown')),
                          retrieved_at=now.isoformat(),age_days=(now.date()-good.index[-1].date()).days)
        from daily_research import enrich_history
        all_dates=pd.to_datetime(ts,unit='s',utc=True).tz_convert(TIMEZONE_NAME).tz_localize(None).normalize()
        return enrich_history(good,q,all_dates)
    except (KeyError,TypeError,ValueError,IndexError,OverflowError):return None


def render_close_research(st, df, symbol):
    from research_dashboard import render_dashboard
    render_dashboard(st, df, symbol)
