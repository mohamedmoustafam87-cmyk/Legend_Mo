from config import TOTAL_CAPITAL, RISK_PER_TRADE


def calculate_risk_management(close_price, atr):
    """
    حساب:
    - Stop Loss
    - حجم الصفقة
    - TP1
    - TP2
    - Risk / Reward
    """

    try:
        close_price = float(close_price)
        atr = float(atr)

        if close_price <= 0 or atr <= 0:
            return None

        stop_loss = close_price - (1.5 * atr)

        if stop_loss <= 0:
            return None

        risk_per_share = close_price - stop_loss

        if risk_per_share <= 0:
            return None

        capital_at_risk = (
            TOTAL_CAPITAL * RISK_PER_TRADE
        )

        if capital_at_risk <= 0:
            return None

        shares_by_risk = int(
            capital_at_risk / risk_per_share
        )

        shares_by_capital = int(
            TOTAL_CAPITAL / close_price
        )

        shares_to_buy = min(
            shares_by_risk,
            shares_by_capital
        )

        if shares_to_buy <= 0:
            return None

        position_value = (
            shares_to_buy * close_price
        )

        actual_risk = (
            shares_to_buy * risk_per_share
        )

        tp_1 = (
            close_price +
            (2 * risk_per_share)
        )

        tp_2 = (
            close_price +
            (3 * risk_per_share)
        )

        rr_1 = (
            (tp_1 - close_price)
            / risk_per_share
        )

        rr_2 = (
            (tp_2 - close_price)
            / risk_per_share
        )

        return {
            "stop_loss": round(stop_loss, 2),
            "risk_per_share": round(risk_per_share, 2),
            "shares": shares_to_buy,
            "position_value": round(position_value, 2),
            "actual_risk": round(actual_risk, 2),
            "tp1": round(tp_1, 2),
            "tp2": round(tp_2, 2),
            "rr1": round(rr_1, 2),
            "rr2": round(rr_2, 2)
        }

    except (
        TypeError,
        ValueError,
        ZeroDivisionError
    ):
        return None
