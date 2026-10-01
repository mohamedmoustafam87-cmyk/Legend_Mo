from config import (
    TOTAL_CAPITAL,
    RISK_PER_TRADE,
    ATR_STOP_MULTIPLIER,
    SUPPORT_ATR_BUFFER,
    TP1_R_MULTIPLE,
    TP2_R_MULTIPLE,
)


# ==========================================================
# Risk Management
# ==========================================================

def calculate_risk_management(
    close_price,
    atr,
    support=None
):
    """
    إدارة مخاطر الصفقة.

    Stop Loss يعتمد على:
    1. الدعم - هامش ATR
    2. أو Close - ATR multiplier

    ويتم اختيار الـ Stop الأوسع.

    الحد الأقصى للمخاطرة:
        TOTAL_CAPITAL × RISK_PER_TRADE
    """

    try:

        close_price = float(
            close_price
        )

        atr = float(
            atr
        )

        if (
            close_price <= 0
            or atr <= 0
        ):
            return None

        # ======================================================
        # Structural Stop
        # ======================================================

        structural_stop = None

        if support is not None:

            support = float(
                support
            )

            if (
                support > 0
                and support < close_price
            ):

                structural_stop = (
                    support -
                    (
                        SUPPORT_ATR_BUFFER *
                        atr
                    )
                )

        # ======================================================
        # ATR Stop
        # ======================================================

        volatility_stop = (
            close_price -
            (
                ATR_STOP_MULTIPLIER *
                atr
            )
        )

        # ======================================================
        # Select Wider Stop
        # ======================================================

        if structural_stop is not None:

            stop_loss = min(
                structural_stop,
                volatility_stop
            )

        else:

            stop_loss = volatility_stop

        # ======================================================
        # Validate
        # ======================================================

        if (
            stop_loss <= 0
            or stop_loss >= close_price
        ):
            return None

        # ======================================================
        # Risk Per Share
        # ======================================================

        risk_per_share = (
            close_price -
            stop_loss
        )

        if risk_per_share <= 0:
            return None

        # ======================================================
        # Maximum Risk
        # ======================================================

        capital_at_risk = (
            TOTAL_CAPITAL *
            RISK_PER_TRADE
        )

        if capital_at_risk <= 0:
            return None

        # ======================================================
        # Position Size - Risk
        # ======================================================

        shares_by_risk = int(
            capital_at_risk /
            risk_per_share
        )

        # ======================================================
        # Position Size - Capital
        # ======================================================

        shares_by_capital = int(
            TOTAL_CAPITAL /
            close_price
        )

        # ======================================================
        # Final Position Size
        # ======================================================

        shares_to_buy = min(
            shares_by_risk,
            shares_by_capital
        )

        if shares_to_buy <= 0:
            return None

        # ======================================================
        # Position Value
        # ======================================================

        position_value = (
            shares_to_buy *
            close_price
        )

        # ======================================================
        # Actual Risk
        # ======================================================

        actual_risk = (
            shares_to_buy *
            risk_per_share
        )

        # ======================================================
        # Take Profit
        # ======================================================

        tp_1 = (
            close_price +
            (
                TP1_R_MULTIPLE *
                risk_per_share
            )
        )

        tp_2 = (
            close_price +
            (
                TP2_R_MULTIPLE *
                risk_per_share
            )
        )

        # ======================================================
        # Risk / Reward
        # ======================================================

        rr_1 = (
            tp_1 -
            close_price
        ) / risk_per_share

        rr_2 = (
            tp_2 -
            close_price
        ) / risk_per_share

        # ======================================================
        # Stop Loss %
        # ======================================================

        stop_loss_pct = (
            (
                close_price -
                stop_loss
            )
            /
            close_price
        ) * 100

        # ======================================================
        # Return
        # ======================================================

        return {

            "stop_loss": round(
                stop_loss,
                2
            ),

            "stop_loss_pct": round(
                stop_loss_pct,
                2
            ),

            "risk_per_share": round(
                risk_per_share,
                2
            ),

            "shares": shares_to_buy,

            "position_value": round(
                position_value,
                2
            ),

            "actual_risk": round(
                actual_risk,
                2
            ),

            "tp1": round(
                tp_1,
                2
            ),

            "tp2": round(
                tp_2,
                2
            ),

            "rr1": round(
                rr_1,
                2
            ),

            "rr2": round(
                rr_2,
                2
            )
        }

    except (
        TypeError,
        ValueError,
        ZeroDivisionError
    ):

        return None
