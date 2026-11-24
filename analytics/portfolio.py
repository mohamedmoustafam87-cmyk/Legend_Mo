"""
محاكاة محفظة مقيّدة برأس المال (100 ألف جنيه) — بديل أمين عن جمع
الصفقات المستقلة الذي يتجاهل التزامن والسيولة المتاحة.

قواعد المحاكاة (معلنة كافتراضات مرشحة):
- رأس مال ابتدائي 100,000 جنيه، بلا إضافات أو سحوبات.
- الصفقات تُفتح بترتيب تاريخ الدخول؛ صفقة جديدة تُفتح فقط إذا كفاها
  النقد المتاح (قيمة الصفقة = shares × entry)، وإلا تُسجَّل skipped_cash.
- النقد يتحرر في تاريخ الخروج (صفقات يوم الخروج متاحة لدخول يوم لاحق فقط —
  تحفظي: لا إعادة استخدام لنقد يوم الخروج نفسه).
- النتيجة: منحنى رأس مال من صافي الصفقات بعد رسوم السيناريو القياسي،
  أقصى عدد صفقات متزامنة، وعدد الصفقات المرفوضة لنقص النقد.
"""

import pandas as pd

from .fee_model import SCENARIO_STANDARD, round_trip_fees

INITIAL_CAPITAL = 100_000.0


def simulate_portfolio(records, capital=INITIAL_CAPITAL, scenario=SCENARIO_STANDARD):
    trades = [r for r in records
              if r.get("outcome") in ("tp1_first", "stop_first", "expired")
              and not r.get("corporate_action_overlap")]
    trades.sort(key=lambda r: (str(r["entry_date"]), r["symbol"]))

    cash = capital
    open_positions = []  # (exit_date, position_value_at_entry, net_pl)
    equity_points = []
    skipped_cash = 0
    max_concurrent = 0
    taken = []

    for r in trades:
        entry_d = pd.Timestamp(r["entry_date"])
        # حرّر النقد للصفقات التي خرجت قبل تاريخ الدخول (تحفظي: ليس في نفس اليوم)
        still_open = []
        for (xd, val, pl) in open_positions:
            if xd < entry_d:
                cash += val + pl
            else:
                still_open.append((xd, val, pl))
        open_positions = still_open

        shares = int(r["shares"])
        entry = float(r["entry_price"])
        # الحجم يُحدُّ بالنقد المتاح: يُخفَض لما يكفي النقد، ويُتخطى إن لم يكفِ لسهم واحد
        capped = min(shares, int(cash / entry))
        if capped <= 0 or shares <= 0:
            skipped_cash += 1
            continue
        shares = capped
        value = shares * entry
        cash -= value
        fees = round_trip_fees(value, shares * float(r["exit_price"]), scenario)
        net_pl = shares * (float(r["exit_price"]) - float(r["entry_price"])) - fees
        open_positions.append((pd.Timestamp(r["exit_date"]), value, net_pl))
        max_concurrent = max(max_concurrent, len(open_positions))
        taken.append(r)

    # صفِّ الباقي
    final_cash = cash + sum(v + pl for (_, v, pl) in open_positions)
    invested = sum(v for (_, v, pl) in open_positions)

    wins = [r for r in taken if r["outcome"] == "tp1_first"]
    return {
        "initial_capital": capital,
        "final_equity": round(final_cash, 2),
        "net_return_pct": round(100 * (final_cash - capital) / capital, 1),
        "trades_taken": len(taken),
        "trades_skipped_cash": skipped_cash,
        "max_concurrent_positions": max_concurrent,
        "open_at_end_invested": round(invested, 2),
        "hit_rate_pct": round(100 * len(wins) / len(taken), 1) if taken else None,
    }
