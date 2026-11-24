import os
from datetime import datetime

from config import (
    ADMIN_CHAT_ID,
    TIMEZONE,
    require_telegram,
)
from signals import REGIME_LABELS

_BOT = None


# =====================================================================
# TELEGRAM BOT (lazy: لا يحتاج TOKEN وقت الاستيراد)
# =====================================================================

def get_bot():
    global _BOT
    if _BOT is None:
        import telebot
        from config import TELEGRAM_TOKEN
        require_telegram()
        _BOT = telebot.TeleBot(TELEGRAM_TOKEN)
    return _BOT


# =====================================================================
# HELPERS
# =====================================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        value = float(value)
        return default if value != value else value
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        return default if value is None else int(float(value))
    except (TypeError, ValueError):
        return default


def num(value, digits=2, default="—"):
    try:
        if value is None:
            return default
        value = float(value)
        return default if value != value else f"{value:,.{digits}f}"
    except (TypeError, ValueError):
        return default


def _is_format_rejection(error):
    # Only an explicit Bot API 400 parsing rejection proves no message was sent.
    result = getattr(error, "result_json", None)
    if not isinstance(result, dict) or result.get("error_code") != 400:
        return False
    description = str(result.get("description", "")).lower()
    return any(marker in description for marker in (
        "can't parse entities", "can't find end of the entity",
        "unsupported start tag", "unclosed start tag",
    ))


def safe_send_message(chat_id, text):
    """Retry plain text only after a definitive formatting rejection."""
    bot = get_bot()
    try:
        bot.send_message(chat_id, text, parse_mode="Markdown")
        return True
    except Exception as error:
        if not _is_format_rejection(error):
            print("Telegram send unconfirmed; no automatic retry. Check receipt before retrying.")
            return False
    try:
        plain = text.replace("*", "").replace("`", "").replace("_", "")
        bot.send_message(chat_id, plain)
        return True
    except Exception:
        print("Plain-text send unconfirmed; no automatic retry. Check receipt before retrying.")
        return False


def _chunk(blocks, header, limit=3800):
    # Split oversized stock blocks at line boundaries, preserving every section.
    # Telegram measures UTF-16 code units, not Python code points.
    def units(text):return len(text.encode("utf-16-le")) // 2
    messages, current = [], header
    for block in blocks:
        # Keep a complete stock block together whenever it fits on one message.
        if units(header + block) <= limit:
            if units(current + block) > limit:
                if current.strip() != header.strip():messages.append(current)
                current = header
            current += block
            continue
        # An oversized stock gets its own parts. Repeat its first two lines,
        # which contain ticker and source session, before each continuation.
        if current.strip() != header.strip():messages.append(current)
        lines = block.splitlines(keepends=True)
        identity = "".join(lines[:2])
        prefix = header + identity
        current = prefix
        sections = "".join(lines[2:]).split("\n\n")
        for section in sections:
            section += "\n\n"
            if units(prefix + section) <= limit:
                if units(current + section) > limit:
                    messages.append(current);current = prefix
                current += section
                continue
            # Only an individually oversized section is split at line boundaries.
            for line in section.splitlines(keepends=True):
                while units(prefix + line) > limit:
                    take = 1
                    while take < len(line) and units(prefix + line[:take+1]) <= limit:take += 1
                    if current.strip() != prefix.strip():messages.append(current)
                    messages.append(prefix + line[:take]);current = prefix;line = line[take:]
                if units(current + line) > limit:
                    messages.append(current);current = prefix
                current += line
        if current.strip() != prefix.strip():messages.append(current)
        current = header
    if current.strip() != header.strip():messages.append(current)
    return messages


DISCLAIMER = (
    "⚠️ _الاحتمالات والنسب تاريخية مُقاسة على بيانات سابقة وليست ضماناً. "
    "التقرير أداة مساعدة وليس توصية استثمارية._"
)


# =====================================================================
# SCANNER REPORT
# =====================================================================

def _context_header(ctx):
    ctx = ctx or {}
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")

    lines = [
        "🏆 *تقرير التحليل الذكي للسوق المصري EGX*",
        f"🕒 {now}",
    ]

    regime = ctx.get("regime")
    if regime:
        b = ctx.get("breadth50")
        lines.append(
            f"🌡️ *حالة السوق:* {REGIME_LABELS.get(regime, regime)}"
            + (f" — `{b:.0f}%` من الأسهم فوق EMA50" if b is not None else "")
        )

    if ctx.get("backtest_available"):
        lines.append(
            f"🧪 *Backtest:* `{ctx.get('backtest_generated', '—')}` "
            f"| نموذج الاحتمالية: {'مفعّل ✅' if ctx.get('meta_validated') else 'غير مفعّل'}"
        )
    else:
        lines.append("⚠️ *لا توجد نتائج backtest* — الإشارات أدناه غير مُتحقق منها. شغّل Backtest.py.")

    if ctx.get("sharia_filter_active") is False:
        lines.append("⚠️ فلتر الأسهم الشرعية غير مفعّل (أضف sharia_stocks.txt).")

    return "\n".join(lines) + "\n━━━━━━━━━━━━━━━━━━\n\n"


def _setup_line(item):
    best = next((s for s in item.get("setups", []) if s["name"] == item.get("best_setup")), None)
    if not best:
        return ""

    parts = [f"🎯 *الإعداد:* {best['label']}"]

    prob = best.get("probability")
    if prob is not None:
        parts.append(f"🔮 *الاحتمالية (نموذج):* `{prob * 100:.0f}%`")

    if best.get("hist_win") is not None:
        parts.append(
            f"📚 *تاريخياً (اختبار خارج العينة):* نجاح `{best['hist_win']:.0f}%` "
            f"| متوسط `{safe_float(best.get('hist_exp')):+.2f}%` بعد التكلفة "
            f"| `{safe_int(best.get('hist_n'))}` صفقة "
            + ("✅" if best.get("validated") else "⚠️ غير مُتحقق")
        )

    if len(item.get("setups", [])) > 1:
        others = [s["label"] for s in item["setups"] if s["name"] != best["name"]]
        parts.append("➕ إعدادات أخرى نشطة: " + "، ".join(others))

    return "\n".join(parts) + "\n"


def format_stock_block(item):
    ticker = item.get("ticker", "N/A")
    current_price = safe_float(item.get("current_price", item.get("price", 0)))
    hist_close = safe_float(item.get("historical_close", item.get("price", 0)))
    change = safe_float(item.get("current_vs_close_pct"))
    realtime = item.get("is_realtime", False)

    price_status = "🟡 آخر إغلاق تاريخي من Yahoo (ليس سعراً لحظياً)"
    as_of = item.get("history_as_of", "غير متاح")

    block = (
        f"📌 *{ticker}* — {item.get('rec', '')}\n"
        f"⭐ Score فني: `{safe_int(item.get('score'))}/100` | الحالة: {item.get('trend_status', '—')}\n"
        + _setup_line(item)
        + "\n"
        f"💵 *السعر المرجعي:* `{current_price:.2f}` ج.م ({change:+.2f}% عن إغلاق `{hist_close:.2f}`)\n"
        f"📡 {price_status} | تاريخ البيانات: {as_of}\n\n"
        f"📍 *الدخول:* `{safe_float(item.get('ideal_entry')):.2f} - {safe_float(item.get('entry_high')):.2f}` "
        f"| {item.get('entry_status', '—')}\n"
        f"🛑 *وقف الخسارة:* `{safe_float(item.get('stop_loss')):.2f}` ({safe_float(item.get('stop_loss_pct')):.2f}%)\n"
        f"🎯 *TP1:* `{safe_float(item.get('tp1')):.2f}` (R:R 1:{safe_float(item.get('rr1')):.2f}) "
        f"| *TP2:* `{safe_float(item.get('tp2')):.2f}`\n"
        f"⏱️ المدة: {item.get('days_tp1_text', '—')}\n\n"
        f"📦 *الكمية المقترحة:* `{safe_int(item.get('shares')):,}` سهم "
        f"(قيمة `{safe_float(item.get('position_value')):,.0f}` | مخاطرة `{safe_float(item.get('actual_risk')):,.0f}` ج.م)\n"
    )

    mult = safe_float(item.get("size_multiplier"), 1.0)
    if mult < 1.0:
        block += f"🌡️ _تم تقليل الحجم إلى {mult:.0%} بسبب حالة السوق_\n"

    block += (
        f"\n📊 RSI `{num(item.get('rsi'), 1)}` | ADX `{num(item.get('adx'), 1)}` | "
        f"حجم `{num(item.get('volume_ratio'))}x` | بعد EMA20 `{safe_float(item.get('distance_from_ema')):+.1f}%`\n"
        f"📍 دعم `{num(item.get('support'))}` | 🚧 مقاومة `{num(item.get('resistance'))}`\n"
    )

    if item.get("rs_rank") == item.get("rs_rank") and item.get("rs_rank") is not None:
        block += f"💪 القوة النسبية: أفضل من `{safe_float(item.get('rs_rank')):.0f}%` من الأسهم\n"

    trail = item.get("trailing_stop")
    block += f"\n🚪 *الخروج:* {item.get('exit_strategy', '')}\n"
    if trail:
        block += f"🛑 وقف المطاردة (Chandelier): `{trail:.2f}`\n"

    reasons = item.get("reasons") or []
    if reasons:
        block += "\n💡 *الأسباب:*\n" + "\n".join(f"• {r}" for r in reasons[:5]) + "\n"

    return block + "\n━━━━━━━━━━━━━━━━━━\n\n"


def format_close_research_block(item):
    from daily_research import format_research
    return format_research(item)


def format_scanner_messages(opportunities, ctx=None):
    ctx = ctx or {}
    research = ctx.get("close_research") or []
    limited = _chunk([format_close_research_block(i) for i in research],
        "التقرير الفني اليومي من Yahoo Finance\nالأسعار مؤرخة وليست أسعار الجلسة الحالية.\n\n") if research else []
    if research and not ctx.get("n_full_analysis") and not opportunities:
        return limited
    header = _context_header(ctx)

    if not opportunities:
        body = "⚠️ لا توجد إشارات مطابقة حالياً — السوق تحت المراقبة.\n"
        n = (ctx or {}).get("n_signals")
        if n:
            body += "عدد الإشارات الخام لكل إعداد: " + ", ".join(f"{k}={v}" for k, v in n.items()) + "\n"
        watch = (ctx or {}).get("watchlist") or []
        if watch:
            body += "\n👀 *مراقبة (بدون إعداد نشط):*\n" + "\n".join(
                f"• {w['ticker']} — Score {w['score']}" for w in watch
            ) + "\n"
        return [header + body + "\n" + DISCLAIMER] + limited

    messages = _chunk([format_stock_block(i) for i in opportunities], header)
    messages[-1] += DISCLAIMER
    return messages + limited


def send_scanner_report(opportunities, ctx=None):
    if (ctx or {}).get("close_research") and os.getenv("FULL_DATED_REPORT_APPROVED") != "true":
        print("New dated full report is review-only. No Telegram message sent.")
        return False
    try:
        results = [safe_send_message(ADMIN_CHAT_ID, message)
                   for message in format_scanner_messages(opportunities, ctx)]
        return bool(results) and all(results)
    except Exception:
        print("Scanner report failed. No credential values were logged.")
        return False


# =====================================================================
# PORTFOLIO REPORT
# =====================================================================

def format_portfolio_messages(results):
    """يرجع قائمة رسائل (تيليجرام حده 4096 حرف) والملخص في الأخيرة."""
    header = "💼 *تقرير متابعة محفظتك الخاصة*\n━━━━━━━━━━━━━━━━━━\n\n"

    blocks = []
    total_value = total_cost = total_pnl = 0.0

    for item in results:
        pnl_pct = safe_float(item.get("pnl_pct"))
        pnl_egp = safe_float(item.get("pnl_egp"))
        total_value += safe_float(item.get("current_value"))
        total_cost += safe_float(item.get("cost_value"))
        total_pnl += pnl_egp

        status = "🟢 السعر الحالي من Mubasher" if item.get("is_realtime") else "🟡 آخر إغلاق Yahoo"
        emoji = "🟢" if pnl_pct >= 0 else "🔴"

        blocks.append(
            f"📌 *السهم:* `{item.get('ticker', 'N/A')}`\n"
            f"📦 *الكمية:* `{safe_int(item.get('shares')):,}` سهم | "
            f"💰 *الشراء:* `{safe_float(item.get('buy_price')):.2f}`\n"
            f"💵 *الحالي:* `{safe_float(item.get('current_price')):.2f}` ج.م — {status}\n"
            f"{emoji} *الربح/الخسارة:* `{pnl_egp:+,.2f}` ج.م (`{pnl_pct:+.2f}%`)\n\n"
            f"💡 *الحالة:* *{item.get('advice', '—')}*\n"
            f"📝 {item.get('reason', '')}\n\n"
            f"⭐ Score `{item.get('score', '—')}/100` | "
            f"📍 دعم `{num(item.get('support'))}` | 🚧 مقاومة `{num(item.get('resistance'))}`\n"
            f"🛑 *وقف المطاردة:* `{num(item.get('stop_loss'))}` | "
            f"🎯 TP1 `{num(item.get('tp1'))}` | TP2 `{num(item.get('tp2'))}`\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
        )

    total_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
    emoji = "🟢" if total_pnl >= 0 else "🔴"

    blocks.append(
        "📊 *ملخص المحفظة*\n━━━━━━━━━━━━━━━━━━\n"
        f"💰 *قيمة المحفظة:* `{total_value:,.2f}` ج.م\n"
        f"{emoji} *إجمالي الأرباح/الخسائر:* `{total_pnl:+,.2f}` ج.م (`{total_pct:+.2f}%`)\n"
    )

    return _chunk(blocks, header)


def send_portfolio_report(results):
    try:
        if not results:
            print("No portfolio data available; portfolio report skipped.")
            return True
        sent = [safe_send_message(ADMIN_CHAT_ID, message)
                for message in format_portfolio_messages(results)]
        return bool(sent) and all(sent)
    except Exception:
        print("Portfolio report failed. No credential values were logged.")
        return False
