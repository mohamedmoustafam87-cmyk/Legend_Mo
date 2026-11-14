from config import (
    TOTAL_CAPITAL,
    RISK_PER_TRADE,
    MAX_POSITION_PCT,
    ATR_STOP_MULTIPLIER,
    SUPPORT_ATR_BUFFER,
    TP1_R_MULTIPLE,
    TP2_R_MULTIPLE,
)


def calculate_risk_management(
    close_price,
    atr,
    support=None,
    stop_atr=None,
    tp1_r=None,
    tp2_r=None,
):
    """
    إدارة مخاطر الصفقة.

    - بدون stop_atr: الوقف = الأوسع بين (الدعم - هامش ATR) و(السعر - ATR×multiplier) كما كان.
    - مع stop_atr (إعداد محدد): الوقف = السعر - stop_atr×ATR (نفس حواجز الـ backtest).

    حجم الصفقة = الأقل بين:
      (رأس المال × RISK_PER_TRADE) / المخاطرة للسهم
      (رأس المال × MAX_POSITION_PCT) / السعر
    """

    try:
        close_price = float(close_price)
        atr = float(atr)

        if close_price <= 0 or atr <= 0:
            return None

        if stop_atr is not None:
            stop_loss = close_price - float(stop_atr) * atr
        else:
            volatility_stop = close_price - ATR_STOP_MULTIPLIER * atr
            stop_loss = volatility_stop

            if support is not None:
                support = float(support)
                if 0 < support < close_price:
                    structural = support - SUPPORT_ATR_BUFFER * atr
                    stop_loss = min(structural, volatility_stop)

        if stop_loss <= 0 or stop_loss >= close_price:
            return None

        risk_per_share = close_price - stop_loss

        capital_at_risk = TOTAL_CAPITAL * RISK_PER_TRADE
        shares_by_risk = int(capital_at_risk / risk_per_share)
        shares_by_capital = int(TOTAL_CAPITAL * MAX_POSITION_PCT / close_price)
        shares = min(shares_by_risk, shares_by_capital)

        if shares <= 0:
            return None

        tp1_r = TP1_R_MULTIPLE if tp1_r is None else float(tp1_r)
        tp2_r = TP2_R_MULTIPLE if tp2_r is None else float(tp2_r)

        tp_1 = close_price + tp1_r * risk_per_share
        tp_2 = close_price + tp2_r * risk_per_share

        return {
            "stop_loss": round(stop_loss, 2),
            "stop_loss_pct": round(risk_per_share / close_price * 100, 2),
            "risk_per_share": round(risk_per_share, 2),
            "shares": shares,
            "position_value": round(shares * close_price, 2),
            "actual_risk": round(shares * risk_per_share, 2),
            "tp1": round(tp_1, 2),
            "tp2": round(tp_2, 2),
            "rr1": round(tp1_r, 2),
            "rr2": round(tp2_r, 2),
        }

    except (TypeError, ValueError, ZeroDivisionError):
        return None
