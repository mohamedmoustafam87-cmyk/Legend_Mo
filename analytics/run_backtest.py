"""
مشغّل القياس التاريخي — يجلب بيانات Yahoo فقط (نفس دالة الإنتاج)،
يخزنها مؤقتًا على القرص، ويشغّل v1_baseline و v2 على نفس البيانات.

الاستخدام:
  TELEGRAM_TOKEN=x ADMIN_CHAT_ID=x python3 -m analytics.run_backtest COMI.CA ETEL.CA
  بدون وسائط = الكون الكامل من config.EGX_STOCKS
"""

import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import fetch_yahoo_history  # Yahoo فقط — قرار المستخدم
from analytics.backtest_v2 import run_symbol_backtest, summarize

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def load_symbol(symbol, max_age_hours=20):
    path = os.path.join(CACHE_DIR, symbol.replace(".", "_") + ".pkl")
    if os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age < max_age_hours * 3600:
            try:
                return pd.read_pickle(path)
            except Exception:
                pass
    df = fetch_yahoo_history(symbol)
    if df is not None and not df.empty:
        df.to_pickle(path)
    return df


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_name = "backtest_results.json"
    for a in sys.argv[1:]:
        if a.startswith("--out="):
            out_name = a.split("=", 1)[1]
    symbols = args or None
    if not symbols:
        from config import EGX_STOCKS
        symbols = EGX_STOCKS

    all_records = []
    failed = []
    for i, sym in enumerate(symbols, 1):
        df = load_symbol(sym)
        if df is None or df.empty:
            failed.append(sym)
            continue
        for variant in ("v1_baseline", "v2"):
            try:
                all_records.extend(run_symbol_backtest(sym, df, variant))
            except Exception as e:
                print(f"⚠️ {sym} {variant}: {type(e).__name__}: {e}")
        if i % 25 == 0:
            print(f"... {i}/{len(symbols)}")

    out = {
        "records": all_records,
        "summary": [summarize(all_records, v) for v in ("v1_baseline", "v2")],
        "failed_symbols": failed,
    }
    out_path = os.path.join(CACHE_DIR, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, default=str, indent=1)
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
    print("failed:", failed)
    print("saved:", out_path)


if __name__ == "__main__":
    main()
