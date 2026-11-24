"""
نموذج رسوم التداول على Thndr (سوق الأسهم المصرية EGX).

المصدر الرسمي: Thndr Help Center - Thndr Order Fees
https://support.thndr.app/en/articles/638558-thndr-order-fees
(آخر تحديث للمقال: 2026-08-18)

مكونات كل أمر (شراء أو بيع)، من المصدر:
- عمولة Thndr: 2 جنيه ثابت + 0.1% من قيمة الأمر.
- EGX: 0.01%
- MCDR: 0.01%
- FRA: 0.005% بحد أدنى 1 جنيه (تُحسب لكل تنفيذ/transaction)
- Risk insurance: 0.005%
- Damgha (ضريبة الدمغة): 0.05%

ملاحظة: مشتركو Thndr Trader (شرط استخدام Thndr X) لديهم 50 أمرًا شهريًا
بدون عمولة Thndr (العمولة فقط، الرسوم الحكومية مستمرة). عدد أوامر المستخدم
الفعلية غير معروف، لذلك يُعرض السيناريوهان كحساسية ولا يُفترض أيٌّ منهما
كخطة المستخدم الفعلية.

هذا النموذج يحسب الرسوم الثابتة والحدود الدنيا على قيمة الأمر الفعلية،
ولا يستخدم نسبة إجمالية تقريبية.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeScenario:
    name: str
    thndr_commission_waived: bool  # سيناريو إعفاء عمولة Thndr (Trader)
    slippage_pct: float            # انزلاق سعري مفترض على سعر التنفيذ


# السيناريو الأساسي: رسوم Thndr القياسية كاملة، بدون انزلاق.
SCENARIO_STANDARD = FeeScenario("standard_full_fees", False, 0.0)
# عمولة Thndr معفاة (حتى 50 أمر/شهر لمشترك Trader)، بدون انزلاق.
SCENARIO_TRADER_WAIVED = FeeScenario("trader_commission_waived", True, 0.0)
# رسوم قياسية + انزلاق 0.5% على التنفيذ (افتراض تحفظي منفصل عن الرسوم).
SCENARIO_STANDARD_SLIPPAGE = FeeScenario("standard_plus_slippage", False, 0.005)

ALL_SCENARIOS = [
    SCENARIO_STANDARD,
    SCENARIO_TRADER_WAIVED,
    SCENARIO_STANDARD_SLIPPAGE,
]


def order_fees(order_value, scenario=SCENARIO_STANDARD):
    """
    رسوم أمر واحد (شراء أو بيع) بقيمة order_value جنيه.
    ترجع إجمالي الرسوم بالجنيه، محسوبة من المكونات الرسمية
    بما فيها الثابت 2 جنيه وحد FRA الأدنى 1 جنيه.
    """
    order_value = float(order_value)
    if order_value <= 0:
        return 0.0

    thndr = 0.0 if scenario.thndr_commission_waived else (
        2.0 + 0.001 * order_value
    )
    egx = 0.0001 * order_value
    mcdr = 0.0001 * order_value
    fra = max(0.00005 * order_value, 1.0)
    risk_insurance = 0.00005 * order_value
    stamp = 0.0005 * order_value

    return thndr + egx + mcdr + fra + risk_insurance + stamp


def round_trip_fees(buy_value, sell_value, scenario=SCENARIO_STANDARD):
    """رسوم الشراء + البيع."""
    return (
        order_fees(buy_value, scenario)
        + order_fees(sell_value, scenario)
    )
