import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import numpy as np
import pandas as pd
import requests

from config import (
    EGX_STOCKS,
    SHARIA_EGX_STOCKS,
    SHARIA_FILTER_ACTIVE,
    MIN_SCORE_THRESHOLD,
    MIN_AVG_DAILY_VALUE,
    MIN_AVG_VOLUME,
    MIN_ACTIVE_DAYS,
    MIN_HISTORY_ROWS,
    MAX_REPORT_STOCKS,
    MAX_WORKERS,
    TIMEZONE,
    TIMEZONE_NAME,
    MARKET_CLOSE,
    BAR_COMPLETE_BUFFER_MIN,
    CONTEXT_FILE,
)

from indicators import calculate_indicators
from signals import market_context, regime_from_breadth
from strategy import evaluate_stock_strategy
from ml import load_model_stats


# ==========================================================
# API Configuration
# ==========================================================

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
MUBASHER_URL = "https://www.mubasher.info/api/1/market/stocks?country=eg"
REQUEST_TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# ==========================================================
# Helpers
# ==========================================================

def clean_symbol(symbol):
    if symbol is None:
        return ""
    return str(symbol).upper().replace(".CA", "").strip()


def safe_float(value, default=None):
    try:
        if value is None:
            return default
        value = float(value)
        return default if pd.isna(value) else value
    except (TypeError, ValueError):
        return default


def _get_json(url, params=None, retries=3):
    last_error = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1) + random.random())
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.6 * (attempt + 1))
    raise last_error


# ==========================================================
# Mubasher Current Prices
# ==========================================================

def fetch_mubasher_prices():
    try:
        payload = _get_json(MUBASHER_URL, retries=2)
        data = payload.get("data", [])

        if not isinstance(data, list):
            return {}

        prices = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            symbol = clean_symbol(item.get("symbol") or item.get("code") or item.get("ticker"))
            price = safe_float(
                item.get("price") or item.get("last") or item.get("lastPrice") or item.get("close")
            )
            if symbol and price is not None and price > 0:
                prices[symbol] = price
        return prices

    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Mubasher price error: {e}")
        return {}


# ==========================================================
# Yahoo Historical Data
# ==========================================================

def drop_incomplete_bar(df, now=None):
    """
    لو آخر شمعة هي شمعة اليوم والجلسة لسه ما خلصتش، نشيلها:
    الحجم والـ High/Low ناقصين وبيبوّظوا كل الإشارات المبنية عليهم.
    """
    if df is None or df.empty:
        return df

    now = now or datetime.now(TIMEZONE)
    close_h, close_m = MARKET_CLOSE
    complete_minutes = close_h * 60 + close_m + BAR_COMPLETE_BUFFER_MIN

    if df.index[-1].date() == now.date() and (now.hour * 60 + now.minute) < complete_minutes:
        return df.iloc[:-1]

    return df


def data_quality_ok(df, max_abs_move_pct=30.0, lookback=120):
    """يستبعد الأسهم اللي فيها قفزات يومية غير منطقية (تقسيم/أسهم مجانية غير معدلة/خطأ بيانات)."""
    if df is None or len(df) < 30:
        return False
    moves = df["Close"].pct_change().abs().tail(lookback) * 100
    return bool((moves.dropna() <= max_abs_move_pct).all())


def fetch_yahoo_history(symbol, period="2y", interval="1d", drop_partial=True):
    try:
        payload = _get_json(
            YAHOO_CHART_URL + symbol,
            params={
                "range": period,
                "interval": interval,
                "events": "history",
                "includeAdjustedClose": "true",
            },
        )

        result = payload.get("chart", {}).get("result")
        if not result:
            return None

        result = result[0]
        timestamps = result.get("timestamp")
        quote = result.get("indicators", {}).get("quote", [])

        if not timestamps or not quote:
            return None

        quote = quote[0]

        index = (
            pd.to_datetime(timestamps, unit="s", utc=True)
            .tz_convert(TIMEZONE_NAME)
            .tz_localize(None)
            .normalize()
        )

        df = pd.DataFrame(
            {
                "Open": quote.get("open"),
                "High": quote.get("high"),
                "Low": quote.get("low"),
                "Close": quote.get("close"),
                "Volume": quote.get("volume"),
            },
            index=index,
        )

        if df.empty:
            return None

        df.index.name = "Date"
        df = df[~df.index.duplicated(keep="last")]

        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).sort_index()

        if drop_partial:
            df = drop_incomplete_bar(df)

        if len(df) < MIN_HISTORY_ROWS:
            return None

        if not data_quality_ok(df):
            print(f"⚠️ Data quality issue (قفزة غير منطقية): {symbol}")
            return None

        return df

    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Yahoo error for {symbol}: {e}")
        return None


# ==========================================================
# Current Price Metadata
# ==========================================================

def get_stock_data(symbol, mubasher_prices=None):

    symbol = str(symbol).upper().strip()
    df = fetch_yahoo_history(symbol)

    if df is None or df.empty:
        return None, "No Data"

    historical_close = safe_float(df["Close"].iloc[-1])

    if historical_close is None or historical_close <= 0:
        return None, "Invalid Historical Data"

    mubasher_price = (mubasher_prices or {}).get(clean_symbol(symbol))

    if mubasher_price is not None and mubasher_price > 0:
        current_price = mubasher_price
        price_source = "Mubasher Current"
        is_realtime = True
        data_source = "Yahoo Historical + Mubasher Current"
    else:
        current_price = historical_close
        price_source = "Yahoo Last Close"
        is_realtime = False
        data_source = "Yahoo Historical + Yahoo Last Close"

    df.attrs.update({
        "symbol": symbol,
        "current_price": current_price,
        "historical_close": historical_close,
        "price_source": price_source,
        "is_realtime": is_realtime,
        "current_vs_close_pct": round((current_price - historical_close) / historical_close * 100, 2),
        "data_source": data_source,
    })

    return df, data_source


def validate_current_price(df):
    if df is None or df.empty:
        return False
    price = safe_float(df.attrs.get("current_price"))
    return price is not None and price > 0


# ==========================================================
# Liquidity Filter
# ==========================================================

def passes_liquidity_filter(df):
    if df is None or df.empty:
        return False

    sample = df.tail(20)
    if len(sample) < 20:
        return False

    avg_daily_value = (sample["Close"] * sample["Volume"]).mean()
    avg_volume = sample["Volume"].mean()
    active_days = int((sample["Volume"] > 0).sum())

    return (
        avg_daily_value >= MIN_AVG_DAILY_VALUE
        and avg_volume >= MIN_AVG_VOLUME
        and active_days >= MIN_ACTIVE_DAYS
    )


# ==========================================================
# Context persistence (للداشبورد والمحفظة)
# ==========================================================

def save_context(ctx, path=CONTEXT_FILE):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ctx, f, ensure_ascii=False)
    except OSError as e:
        print(f"⚠️ Could not save market context: {e}")


def load_saved_context(path=CONTEXT_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ==========================================================
# Scan
# ==========================================================

def _load_one(symbol, mubasher_prices):
    """Yahoo + فلتر السيولة + مؤشرات. يرجع (symbol, df|None)."""
    try:
        time.sleep(random.random() * 0.3)

        df, data_source = get_stock_data(symbol, mubasher_prices)

        if df is None or not validate_current_price(df):
            return symbol, None

        if not passes_liquidity_filter(df):
            return symbol, None

        meta = dict(df.attrs)
        meta.setdefault("data_source", data_source)

        df = calculate_indicators(df)
        if df is None:
            return symbol, None

        df.attrs.update(meta)
        return symbol, df

    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Error loading {symbol}: {e}")
        return symbol, None


def load_universe_frames(symbols, mubasher_prices):
    dfs = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_load_one, s, mubasher_prices) for s in symbols]
        for fut in as_completed(futures):
            symbol, df = fut.result()
            if df is not None:
                dfs[symbol] = df
    return dfs


def scan_market(return_context=False):

    print("🔎 Starting market scan...")

    mubasher_prices = fetch_mubasher_prices()
    print(
        f"📡 Mubasher prices loaded: {len(mubasher_prices)} stocks"
        if mubasher_prices else "⚠️ Mubasher unavailable. Using Yahoo Last Close."
    )

    universe = [s for s in EGX_STOCKS if s in set(SHARIA_EGX_STOCKS)]
    dfs = load_universe_frames(universe, mubasher_prices)
    print(f"📈 Tradable stocks loaded: {len(dfs)} / {len(universe)}")

    ctx = market_context(dfs) if dfs else {}
    stats = load_model_stats()

    ctx.update({
        "n_universe": len(universe),
        "sharia_filter_active": SHARIA_FILTER_ACTIVE,
        "backtest_available": stats is not None,
        "backtest_generated": (stats or {}).get("generated"),
        "meta_validated": bool(((stats or {}).get("meta") or {}).get("validated")),
    })

    if ctx.get("regime") is None:
        ctx["regime"] = regime_from_breadth(None)

    results = []

    for symbol, df in dfs.items():
        try:
            analysis = evaluate_stock_strategy(df, symbol)
            if analysis is None:
                continue

            for key in (
                "current_price", "historical_close", "current_vs_close_pct",
                "price_source", "is_realtime", "data_source",
            ):
                analysis[key] = df.attrs.get(key)

            analysis["strategy_price"] = analysis.get("price", df.attrs.get("historical_close"))
            results.append(analysis)

        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Error scanning {symbol}: {e}")

    actionable = [r for r in results if r.get("actionable")]
    actionable.sort(key=lambda x: (x.get("edge_score", 0), x.get("score", 0)), reverse=True)

    watch = sorted(
        [r for r in results if not r.get("actionable") and r.get("score", 0) >= 70],
        key=lambda x: x.get("score", 0),
        reverse=True,
    )[:3]

    ctx["n_signals"] = {
        name: sum(1 for r in results if any(s["name"] == name for s in r.get("setups", [])))
        for name in ("short_term", "mean_reversion", "pullback", "breakout", "momentum")
    }
    ctx["watchlist"] = [
        {"ticker": r["ticker"], "score": r["score"], "rec": r["rec"]} for r in watch
    ]

    print(f"📊 Qualified stocks: {len(actionable)}")

    if ctx.get("rs_quantiles"):
        save_context({k: v for k, v in ctx.items() if k != "watchlist"})

    top = actionable[:MAX_REPORT_STOCKS]

    return (top, ctx) if return_context else top
