"""
منطق الإشارة المُرقّى (v2) — نسخة معزولة للاختبار فقط.

المواصفة المعتمدة من المستخدم (24 نوفمبر 2026):
1. بوابات إلزامية (ليست نقاطًا): السعر > MA200، و EMA20 > EMA50.
2. الإبقاء على فلتر السيولة ورفض RSI > 72 (موجودان أصلًا في مسار v1).
3. توحيد مسافة EMA20 (المرشح الأول 5%): فوقها WAIT ولا تُعرض كشراء.
4. الدخول مشروط: تجاوز قمة جلسة الإشارة خلال 3 جلسات وإلا «لم يُنفذ».
5. وقف/هدف/حجم موحّد من سعر التنفيذ الفعلي؛ TP1=2R و TP2=3R.
6. قاعدة مقاومة ثابتة (بيانات ما قبل الإشارة) لا تقف قبل TP1.
7. أوزان السكور بدون تغيير: يستخدم دالة الإنتاج نفسها مع min_score=None
   (دالة الإنتاج هي المصدر الوحيد للسكور — لا إعادة تنفيذ للأوزان).

الاختيارات المرشحة (قابلة للعكس، مميّزة عن المعتمد النهائي):
- [CANDIDATE-A] المقاومة = Resistance_20 الحالية (أعلى قمة 20 جلسة سابقة).
- [CANDIDATE-B] صفقة واحدة مفتوحة لكل سهم حتى تُغلق نتيجتها.
- [CANDIDATE-C] الكون = كامل قائمة EGX مع فلتر سيولة متحرك لكل تاريخ.
"""

from dataclasses import dataclass, field

from config import (
    MIN_SCORE_THRESHOLD,
    MIN_AVG_DAILY_VALUE,
    MIN_AVG_VOLUME,
    TOTAL_CAPITAL,
    RISK_PER_TRADE,
)
from strategy import evaluate_stock_strategy

EMA20_MAX_DISTANCE_PCT = 5.0   # المرشح الأول المعتمد لتوحيد المسافة
EMA20_MIN_DISTANCE_PCT = -10.0

ENTRY_WINDOW_SESSIONS = 3      # الدخول خلال 3 جلسات من الإشارة
MEASUREMENT_HORIZON = 42       # أفق القياس المعتمد
TICK = 0.01                    # أقل خطوة سعر (جنيه)


@dataclass
class SignalV2:
    symbol: str
    signal_date: object
    score: int
    close: float
    signal_high: float
    atr: float
    support: float
    resistance: float
    tp1_estimate: float
    stop_at_close: float
    status: str = "BUY"        # BUY أو WAIT (WAIT لا يُنفَّذ كشراء)
    wait_reason: str = ""
    gates: dict = field(default_factory=dict)
    analysis: dict = field(default_factory=dict)


def liquidity_ok_on(df):
    """فلتر السيولة الحالي نفسه على آخر 20 جلسة حتى تاريخ الإشارة (سببي)."""
    sample = df.tail(20)
    if len(sample) < 20:
        return False
    return (
        (sample["Close"] * sample["Volume"]).mean() >= MIN_AVG_DAILY_VALUE
        and sample["Volume"].mean() >= MIN_AVG_VOLUME
    )


def stop_rule(price, support, atr):
    """قاعدة الوقف الحالية (risk.py) معاد تطبيقها على أي سعر مرجعي."""
    structural = support - 0.5 * atr if 0 < support < price else None
    volatility_stop = price - 2.0 * atr
    stop = (
        min(structural, volatility_stop)
        if structural is not None else volatility_stop
    )
    return stop if 0 < stop < price else None


def evaluate_signal_v2(df, symbol, ema_max_dist=EMA20_MAX_DISTANCE_PCT):
    """
    df: مقصوص حتى جلسة الإشارة شاملةً إياها، بالمؤشرات محسوبة مسبقًا.
    يعيد SignalV2 أو None إن فشلت بوابة إلزامية.
    """
    if df is None or len(df) < 220:
        return None

    # السكور من دالة الإنتاج نفسها (أوزان v1 بدون أي تغيير)
    analysis = evaluate_stock_strategy(df.copy(), symbol, min_score=None)
    if analysis is None:
        return None

    latest = df.iloc[-1]
    close = float(latest["Close"])
    ma200 = float(latest["MA_200"])
    ema20 = float(latest["EMA_20"])
    ema50 = float(latest["EMA_50"])
    signal_high = float(latest["High"])
    atr = float(analysis["atr"])
    support = float(analysis["support"])
    resistance = float(analysis["resistance"])

    gates = {}
    # البوابات الإلزامية المعتمدة
    gates["price_above_ma200"] = close > ma200
    gates["ema20_above_ema50"] = ema20 > ema50
    # RSI<=72 مفروض أصلًا داخل دالة الإنتاج (ترجع None لو تجاوزه)
    gates["liquidity"] = liquidity_ok_on(df)
    if not all(gates.values()):
        return None

    # حد السكور (مثل السكانر: أقل من 60 لا تظهر)
    if analysis["score"] < MIN_SCORE_THRESHOLD:
        return None

    # مسافة EMA20 الموحدة (مرشح 5%) — WAIT ولا يُنفَّذ كشراء
    distance_from_ema = float(analysis["distance_from_ema"])
    status = "BUY"
    wait_reason = ""
    if distance_from_ema > ema_max_dist:
        status = "WAIT"
        wait_reason = f"السعر ممتد فوق EMA20 ({distance_from_ema:.1f}%)"
    elif distance_from_ema < EMA20_MIN_DISTANCE_PCT:
        status = "WAIT"
        wait_reason = f"السعر بعيد أسفل المتوسطات ({distance_from_ema:.1f}%)"

    # قاعدة الوقف من سعر إغلاق الإشارة + بوابة المقاومة [CANDIDATE-A]
    stop_at_close = stop_rule(close, support, atr)
    if stop_at_close is None:
        return None
    r_per_share = close - stop_at_close
    tp1_estimate = close + 2.0 * r_per_share
    gates["resistance_room"] = not (close < resistance < tp1_estimate)
    if not gates["resistance_room"]:
        return None

    return SignalV2(
        symbol=symbol,
        signal_date=df.index[-1],
        score=int(analysis["score"]),
        close=close,
        signal_high=signal_high,
        atr=atr,
        support=support,
        resistance=resistance,
        tp1_estimate=round(tp1_estimate, 4),
        stop_at_close=round(stop_at_close, 4),
        status=status,
        wait_reason=wait_reason,
        gates=gates,
        analysis=analysis,
    )


def position_size(entry_price, stop_price):
    """نفس منطق risk.py: مخاطرة 1% من رأس المال، بحد أقصى قيمة المحفظة."""
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return 0
    shares_by_risk = int((TOTAL_CAPITAL * RISK_PER_TRADE) / risk_per_share)
    shares_by_capital = int(TOTAL_CAPITAL / entry_price)
    return max(0, min(shares_by_risk, shares_by_capital))
