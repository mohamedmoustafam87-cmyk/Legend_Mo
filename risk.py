from config import TOTAL_CAPITAL, RISK_PER_TRADE

def calculate_risk_management(close_price, atr):
    try:
        stop_loss = round(close_price - (1.5 * atr), 2)
        risk_per_share = close_price - stop_loss

        if risk_per_share <= 0:
            return None

        capital_at_risk = TOTAL_CAPITAL * RISK_PER_TRADE
        shares_to_buy = int(capital_at_risk / risk_per_share)

        tp_1 = round(close_price + (2 * risk_per_share), 2)
        tp_2 = round(close_price + (3 * risk_per_share), 2)

        return {
            'stop_loss': stop_loss,
            'shares': shares_to_buy,
            'tp1': tp_1,
            'tp2': tp_2
        }

    except Exception as e:
        return None
