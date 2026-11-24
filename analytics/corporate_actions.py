"""
كشف الأحداث المؤسسية (توزيعات/تجزئة) من Yahoo نفسها (events=div,splits)
واستبعاد الصفقات التي يمتد احتجازها عبر حدث — البيانات الخام غير معدّلة،
فتلك الصفقات قد تكون أرقامها مشوهة. يُفصح عن العينة المستبعدة ولا تُعدَّل
الأسعار (البقاء على نفس مصدر الإنتاج الخام).
"""

import json
import os
import time

import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_corporate_actions(symbol, max_age_hours=72):
    """يعيد قائمة تواريخ الأحداث المؤسسية (dividends + splits) لسهم."""
    path = os.path.join(CACHE_DIR, symbol.replace(".", "_") + "_events.json")
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < max_age_hours * 3600:
        try:
            return json.load(open(path))
        except Exception:
            pass
    dates = []
    try:
        resp = requests.get(
            YAHOO_CHART_URL + symbol,
            params={"range": "2y", "interval": "1d", "events": "div,splits"},
            headers=YAHOO_HEADERS, timeout=30)
        if resp.status_code == 200:
            result = resp.json().get("chart", {}).get("result") or []
            if result:
                events = result[0].get("events") or {}
                for kind in ("dividends", "splits"):
                    for ev in (events.get(kind) or {}).values():
                        dates.append({"kind": kind, "ts": ev.get("date")})
    except Exception:
        pass
    json.dump(dates, open(path, "w"))
    return dates


def mark_corporate_action_trades(records, symbol_events):
    """
    يوسم الصفقات الممتدة عبر حدث مؤسسي كـ corporate_action_overlap.
    symbol_events: {symbol: [iso_date_str]}.
    """
    import pandas as pd
    marked = 0
    for r in records:
        if r.get("outcome") not in ("tp1_first", "stop_first", "expired"):
            continue
        dates = symbol_events.get(r["symbol"]) or []
        if not dates:
            continue
        try:
            entry = pd.Timestamp(r["entry_date"]).tz_localize(None)
            exit_ = pd.Timestamp(r["exit_date"]).tz_localize(None)
        except Exception:
            continue
        for d in dates:
            if entry <= pd.Timestamp(d).tz_localize(None) <= exit_:
                r["corporate_action_overlap"] = True
                marked += 1
                break
    return marked
