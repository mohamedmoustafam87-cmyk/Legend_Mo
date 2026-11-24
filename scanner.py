import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

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
    raise last_error or RuntimeError("Data provider unavailable")


# ==========================================================
# Mubasher Current Prices
# ==========================================================

def fetch_mubasher_prices():
    """Compatibility no-op. Yahoo-only mode never queries another provider."""
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


def latest_expected_session(now=None):
    """Conservative expected complete daily session under configured calendar."""
    now = now or datetime.now(TIMEZONE)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware current time required")
    now = now.astimezone(TIMEZONE)
    session = now.date()
    ready = MARKET_CLOSE[0] * 60 + MARKET_CLOSE[1] + BAR_COMPLETE_BUFFER_MIN
    if now.hour * 60 + now.minute < ready:
        session -= timedelta(days=1)
    from config import TRADING_WEEKDAYS, EGX_HOLIDAYS
    for _ in range(370):
        if session.weekday() in TRADING_WEEKDAYS and session.isoformat() not in EGX_HOLIDAYS:
            return session
        session -= timedelta(days=1)
    raise ValueError("Calendar has no valid session")


def data_quality_ok(df, max_abs_move_pct=30.0, lookback=120):
    """Reject inconsistent bars rather than manufacture corrected prices."""
    if df is None or len(df) < 30:
        return False
    columns = ["Open", "High", "Low", "Close", "Volume"]
    if any(c not in df.columns for c in columns):
        return False
    values = df[columns].to_numpy(float)
    if not np.isfinite(values).all():
        return False
    if (df[["Open", "High", "Low", "Close"]] <= 0).any().any() or (df["Volume"] < 0).any():
        return False
    epsilon = df["Close"].abs() * 1e-6
    if ((df["High"] + epsilon < df[["Open", "Close", "Low"]].max(axis=1)) |
            (df["Low"] - epsilon > df[["Open", "Close", "High"]].min(axis=1))).any():
        return False
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        return False
    moves = df["Close"].pct_change().abs().tail(lookback) * 100
    return bool((moves.dropna() <= max_abs_move_pct).all())


def history_metadata_ok(meta, symbol):
    # This app's position sizing and P&L assume Egyptian-pound EGX equities.
    return (meta.get("symbol") == symbol
            and meta.get("currency") == "EGP"
            and meta.get("exchangeName") in ("CAI", "EGX")
            and meta.get("exchangeTimezoneName") == TIMEZONE_NAME
            and meta.get("instrumentType") == "EQUITY")


def fetch_yahoo_history(symbol, period="2y", interval="1d", drop_partial=True):
    # Existing analysis is daily only. Never relabel intraday bars as sessions.
    if interval != "1d":
        print("Data unavailable: intraday analysis is not supported by this daily loader")
        return None
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
        meta = result.get("meta") or {}
        if meta.get("dataGranularity") != interval:
            print(f"Data unavailable: provider candle timeframe mismatch for {symbol}")
            return None
        if not history_metadata_ok(meta, symbol):
            print(f"Data unavailable: provider instrument metadata mismatch for {symbol}")
            return None
        timestamps = result.get("timestamp")
        quote = result.get("indicators", {}).get("quote", [])

        if not timestamps or not quote:
            return None

        quote = quote[0]
        required_fields = ("open", "high", "low", "close", "volume")
        if (not isinstance(timestamps, list)
                or any(not isinstance(quote.get(k), list)
                       or len(quote[k]) != len(timestamps) for k in required_fields)):
            print(f"Data unavailable: provider candle arrays mismatch for {symbol}")
            return None
        if any(not isinstance(t, (int, float)) or isinstance(t, bool)
               or not np.isfinite(t) for t in timestamps):
            print(f"Data unavailable: invalid provider timestamp for {symbol}")
            return None
        if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
            print(f"Data unavailable: duplicate or unordered provider timestamps for {symbol}")
            return None

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
        if df.index.has_duplicates:
            print(f"Data unavailable: multiple candles in daily session for {symbol}")
            return None

        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Remove only an explicitly unfinished current-session candle. Missing
        # completed candles remain invalid; never hide them with dropna/sorting.
        if drop_partial:
            df = drop_incomplete_bar(df)

        if len(df) < MIN_HISTORY_ROWS:
            return None

        now = datetime.now(TIMEZONE)
        if df.index[-1].date() > now.date():
            print(f"Data unavailable: future session for {symbol}")
            return None
        if df.index[-1].date() < latest_expected_session(now):
            print(f"Data unavailable: latest complete session is missing for {symbol}")
            return None

        if not data_quality_ok(df):
            print(f"⚠️ Data quality issue (قفزة غير منطقية): {symbol}")
            return None

        df.attrs.update({
            "history_as_of": df.index[-1].date().isoformat(),
            "retrieved_at": now.isoformat(),
            "currency": meta["currency"],
            "exchange": meta["exchangeName"],
            "price_basis": "Yahoo OHLC; split-adjusted close, not dividend total return",
            "provider_delay_minutes": 20,
        })
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

    # The legacy Mubasher map contains no exchange/currency/as-of evidence.
    # Keep the argument for compatibility, but do not use it for a current quote.
    current_price = historical_close
    price_source = "Yahoo Last Complete Close"
    is_realtime = False
    data_source = "Yahoo validated daily history (not a live quote)"

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

    mubasher_prices = {}  # Legacy argument only, no secondary data source.
    print("Yahoo-only daily reference mode; not a live quote or intraday feed.")

    universe = [s for s in EGX_STOCKS if s in set(SHARIA_EGX_STOCKS)]
    dfs = load_universe_frames(universe, mubasher_prices)
    print(f"📈 Tradable stocks loaded: {len(dfs)} / {len(universe)}")

    if not dfs:
        raise RuntimeError("No validated market data; no market report should be sent")
    ctx = market_context(dfs)
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
                "history_as_of", "retrieved_at", "currency", "price_basis",
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
