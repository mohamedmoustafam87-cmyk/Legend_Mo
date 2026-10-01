import telebot

from config import (
    TELEGRAM_TOKEN,
    ADMIN_CHAT_ID
)


# =====================================================================
# TELEGRAM BOT
# =====================================================================

bot = telebot.TeleBot(
    TELEGRAM_TOKEN
)


# =====================================================================
# HELPERS
# =====================================================================

def safe_float(value, default=0.0):
    """
    تحويل آمن إلى float.
    يمنع التقرير من التوقف بسبب None / NaN / قيمة غير رقمية.
    """
    try:
        if value is None:
            return default

        value = float(value)

        if value != value:  # NaN
            return default

        return value

    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    """
    تحويل آمن إلى integer.
    """
    try:
        if value is None:
            return default

        return int(float(value))

    except (TypeError, ValueError):
        return default


def safe_send_message(chat_id, text):
    """
    إرسال رسالة Telegram.
    إذا فشل Markdown يتم إرسالها كنص عادي.
    """
    try:
        bot.send_message(
            chat_id,
            text,
            parse_mode="Markdown"
        )
        return True

    except Exception:
        try:
            plain_text = (
                text
                .replace("*", "")
                .replace("`", "")
                .replace("_", "")
            )

            bot.send_message(
                chat_id,
                plain_text
            )

            return True

        except Exception as e:
            print(
                f"❌ Telegram send error: {e}"
            )
            return False


# =====================================================================
# SCANNER REPORT
# =====================================================================

def send_scanner_report(opportunities):

    try:

        # -------------------------------------------------------------
        # NO OPPORTUNITIES
        # -------------------------------------------------------------

        if not opportunities:

            safe_send_message(
                ADMIN_CHAT_ID,
                (
                    "📊 *تقرير السوق المصري EGX*\n\n"
                    "⚠️ لا توجد أسهم حققت الحد الأدنى "
                    "من شروط الاستراتيجية حالياً.\n\n"
                    "🔎 السوق تحت المراقبة."
                )
            )

            return

        # -------------------------------------------------------------
        # SORT TOP 5
        # -------------------------------------------------------------

        opportunities = sorted(
            opportunities,
            key=lambda x: safe_float(
                x.get("score")
            ),
            reverse=True
        )[:5]

        messages = []

        current_message = (
            "🏆 *تقرير التحليل الذكي للسوق المصري EGX*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📈 *الاستراتيجية: التوقعات المستقبلية "
            "(شهر + شهرين)*\n"
            "🎯 *الهدف: اختيار السهم + توقيت الدخول "
            "+ إدارة المخاطر والخروج*\n\n"
        )

        # -------------------------------------------------------------
        # EACH STOCK
        # -------------------------------------------------------------

        for item in opportunities:

            try:

                # =====================================================
                # BASIC DATA
                # =====================================================

                ticker = item.get(
                    "ticker",
                    "N/A"
                )

                score = safe_int(
                    item.get("score")
                )

                recommendation = item.get(
                    "rec",
                    "🟡 WATCH"
                )

                # =====================================================
                # PRICE DATA
                # =====================================================

                # السعر الحالي من Mubasher
                # أو Yahoo Last Close في حالة فشل Mubasher
                current_price = safe_float(
                    item.get(
                        "current_price",
                        item.get("price", 0)
                    )
                )

                # آخر إغلاق تاريخي من Yahoo
                historical_close = safe_float(
                    item.get(
                        "historical_close",
                        item.get("price", 0)
                    )
                )

                price_source = item.get(
                    "price_source",
                    item.get(
                        "data_source",
                        "غير محدد"
                    )
                )

                data_source = item.get(
                    "data_source",
                    "غير محدد"
                )

                is_realtime = item.get(
                    "is_realtime",
                    False
                )

                current_vs_close_pct = safe_float(
                    item.get(
                        "current_vs_close_pct"
                    )
                )

                # =====================================================
                # PRICE STATUS
                # =====================================================

                if is_realtime:

                    price_status = (
                        "🟢 *السعر الحالي من Mubasher*"
                    )

                else:

                    price_status = (
                        "🟡 *Mubasher غير متاح — "
                        "تم استخدام آخر إغلاق Yahoo*"
                    )

                # =====================================================
                # FORECAST
                # =====================================================

                trend_status = item.get(
                    "trend_status",
                    "غير متوفر"
                )

                forecast_1m_score = safe_int(
                    item.get(
                        "forecast_1m_score"
                    )
                )

                forecast_2m_score = safe_int(
                    item.get(
                        "forecast_2m_score"
                    )
                )

                forecast_1m_status = item.get(
                    "forecast_1m_status",
                    "غير متوفر"
                )

                forecast_2m_status = item.get(
                    "forecast_2m_status",
                    "غير متوفر"
                )

                # =====================================================
                # ENTRY
                # =====================================================

                entry_status = item.get(
                    "entry_status",
                    "غير متوفر"
                )

                ideal_entry = safe_float(
                    item.get(
                        "ideal_entry",
                        current_price
                    )
                )

                entry_high = safe_float(
                    item.get(
                        "entry_high",
                        current_price
                    )
                )

                distance_from_ema = safe_float(
                    item.get(
                        "distance_from_ema"
                    )
                )

                # =====================================================
                # TECHNICAL INDICATORS
                # =====================================================

                ma200_slope = safe_float(
                    item.get(
                        "ma200_slope"
                    )
                )

                ema50_slope = safe_float(
                    item.get(
                        "ema50_slope"
                    )
                )

                volume_ratio = safe_float(
                    item.get(
                        "volume_ratio"
                    )
                )

                atr = safe_float(
                    item.get(
                        "atr"
                    )
                )

                support = safe_float(
                    item.get(
                        "support"
                    )
                )

                resistance = safe_float(
                    item.get(
                        "resistance"
                    )
                )

                # =====================================================
                # RISK MANAGEMENT
                # =====================================================

                shares = safe_int(
                    item.get(
                        "shares"
                    )
                )

                stop_loss = safe_float(
                    item.get(
                        "stop_loss"
                    )
                )

                stop_loss_pct = safe_float(
                    item.get(
                        "stop_loss_pct"
                    )
                )

                position_value = safe_float(
                    item.get(
                        "position_value"
                    )
                )

                actual_risk = safe_float(
                    item.get(
                        "actual_risk"
                    )
                )

                risk_per_share = safe_float(
                    item.get(
                        "risk_per_share"
                    )
                )

                tp1 = safe_float(
                    item.get(
                        "tp1"
                    )
                )

                tp2 = safe_float(
                    item.get(
                        "tp2"
                    )
                )

                rr1 = safe_float(
                    item.get(
                        "rr1"
                    )
                )

                rr2 = safe_float(
                    item.get(
                        "rr2"
                    )
                )

                days_tp1_text = item.get(
                    "days_tp1_text",
                    "غير متوفر"
                )

                days_tp2_text = item.get(
                    "days_tp2_text",
                    "غير متوفر"
                )

                exit_strategy = item.get(
                    "exit_strategy",
                    "🟢 الوضع آمن"
                )

                # =====================================================
                # ENTRY MESSAGE
                # =====================================================

                if str(
                    entry_status
                ).startswith("🟢"):

                    entry_message = (
                        "🟢 *الدخول مناسب حالياً*"
                    )

                elif str(
                    entry_status
                ).startswith("🟡"):

                    entry_message = (
                        "🟡 *انتظر نقطة دخول أفضل*"
                    )

                else:

                    entry_message = (
                        "🔴 *لا يوجد دخول حالياً*"
                    )

                # =====================================================
                # REASONS
                # =====================================================

                reasons = item.get(
                    "reasons",
                    []
                )

                if not isinstance(
                    reasons,
                    (list, tuple)
                ):
                    reasons = [str(reasons)]

                # =====================================================
                # STOCK MESSAGE
                # =====================================================

                stock_message = (
                    f"📌 *السهم:* `{ticker}`\n"
                    f"⭐ *Score:* `{score}/100`\n"
                    f"🎯 *التوصية:* {recommendation}\n\n"

                    # -------------------------------------------------
                    # PRICE
                    # -------------------------------------------------

                    f"💵 *السعر الحالي:* "
                    f"`{current_price:.2f}` ج.م\n"

                    f"📊 *آخر إغلاق للتحليل:* "
                    f"`{historical_close:.2f}` ج.م\n"

                    f"📈 *التغير من آخر إغلاق:* "
                    f"`{current_vs_close_pct:+.2f}%`\n"

                    f"📡 *مصدر السعر:* "
                    f"`{price_source}`\n"

                    f"{price_status}\n\n"

                    # -------------------------------------------------
                    # FORECAST
                    # -------------------------------------------------

                    f"📈 *التوقعات المستقبلية:*\n"
                    f"• الشهر القادم: "
                    f"`{forecast_1m_score}/100` "
                    f"({forecast_1m_status})\n"

                    f"• الشهرين القادمين: "
                    f"`{forecast_2m_score}/100` "
                    f"({forecast_2m_status})\n"

                    f"• الحالة العامة: "
                    f"{trend_status}\n\n"

                    # -------------------------------------------------
                    # ENTRY
                    # -------------------------------------------------

                    f"🎯 *منطقة الدخول المقترحة:*\n"
                    f"`{ideal_entry:.2f} - "
                    f"{entry_high:.2f}` ج.م\n"

                    f"📊 {entry_message}\n"

                    f"📏 *البعد عن EMA20:* "
                    f"`{distance_from_ema:+.1f}%`\n\n"

                    # -------------------------------------------------
                    # INDICATORS
                    # -------------------------------------------------

                    f"📊 *المؤشرات الرئيسية:*\n"

                    f"• MA200 Slope: "
                    f"`{ma200_slope:+.2f}%`\n"

                    f"• EMA50 Slope: "
                    f"`{ema50_slope:+.2f}%`\n"

                    f"• Volume: "
                    f"`{volume_ratio:.2f}x`\n"

                    f"• ATR: "
                    f"`{atr:.2f}`\n\n"

                    # -------------------------------------------------
                    # RISK
                    # -------------------------------------------------

                    f"🛑 *Stop Loss:* "
                    f"`{stop_loss:.2f}` ج.م "
                    f"(`{stop_loss_pct:.2f}%`)\n"

                    f"⚠️ *المخاطرة للسهم:* "
                    f"`{risk_per_share:.2f}` ج.م\n\n"

                    f"📦 *الكمية المقترحة:* "
                    f"`{shares:,}` سهم\n"

                    f"💰 *قيمة الصفقة:* "
                    f"`{position_value:,.2f}` ج.م\n"

                    f"⚠️ *المخاطرة الفعلية:* "
                    f"`{actual_risk:,.2f}` ج.م\n\n"

                    # -------------------------------------------------
                    # TARGETS
                    # -------------------------------------------------

                    f"🎯 *الهدف الأول TP1:* "
                    f"`{tp1:.2f}` ج.م "
                    f"(Risk/Reward: `1:{rr1:.2f}`)\n"

                    f"⏱️ المدة المتوقعة: "
                    f"`{days_tp1_text}`\n"

                    f"🎯 *الهدف الثاني TP2:* "
                    f"`{tp2:.2f}` ج.م "
                    f"(Risk/Reward: `1:{rr2:.2f}`)\n"

                    f"⏱️ المدة المتوقعة: "
                    f"`{days_tp2_text}`\n\n"

                    # -------------------------------------------------
                    # LEVELS
                    # -------------------------------------------------

                    f"📍 *الدعم:* "
                    f"`{support:.2f}` ج.م\n"

                    f"🚧 *المقاومة:* "
                    f"`{resistance:.2f}` ج.م\n\n"

                    # -------------------------------------------------
                    # EXIT
                    # -------------------------------------------------

                    f"🚪 *خطة وإشارات الخروج:*\n"
                    f"{exit_strategy}\n\n"

                    # -------------------------------------------------
                    # REASONS
                    # -------------------------------------------------

                    f"💡 *أسباب التقييم:*\n"
                )

                if reasons:

                    for reason in reasons:
                        stock_message += (
                            f"• {reason}\n"
                        )

                else:

                    stock_message += (
                        "• لا توجد تفاصيل إضافية.\n"
                    )

                stock_message += (
                    "\n━━━━━━━━━━━━━━━━━━\n\n"
                )

                # =====================================================
                # TELEGRAM MESSAGE LIMIT
                # =====================================================

                if len(
                    current_message + stock_message
                ) > 3800:

                    messages.append(
                        current_message
                    )

                    current_message = (
                        "🏆 *تكملة تقرير السوق المصري EGX*\n\n"
                        + stock_message
                    )

                else:

                    current_message += (
                        stock_message
                    )

            except Exception as e:

                print(
                    f"⚠️ Error formatting "
                    f"{item.get('ticker', 'Unknown')}: {e}"
                )

                continue

        # -------------------------------------------------------------
        # ADD LAST MESSAGE
        # -------------------------------------------------------------

        if current_message.strip():

            messages.append(
                current_message
            )

        # -------------------------------------------------------------
        # SEND ALL MESSAGES
        # -------------------------------------------------------------

        for message in messages:

            safe_send_message(
                ADMIN_CHAT_ID,
                message
            )

    except Exception as e:

        print(
            f"❌ Error sending scanner report: {e}"
        )
