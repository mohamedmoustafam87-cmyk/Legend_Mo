import telebot

from config import (
    TELEGRAM_TOKEN,
    ADMIN_CHAT_ID
)


# ==========================================================
# Telegram Bot
# ==========================================================

bot = telebot.TeleBot(
    TELEGRAM_TOKEN
)


# ==========================================================
# Send Scanner Report
# ==========================================================

def send_scanner_report(opportunities):

    try:

        # ==========================================================
        # No Opportunities
        # ==========================================================

        if not opportunities:

            bot.send_message(
                ADMIN_CHAT_ID,
                (
                    "📊 *تقرير السوق المصري EGX*\n\n"
                    "⚠️ لا توجد أسهم حققت الحد الأدنى "
                    "من شروط الاستراتيجية حالياً.\n\n"
                    "🔎 السوق تحت المراقبة."
                ),
                parse_mode="Markdown"
            )

            return


        messages = []

        current_message = (
            "🏆 *تقرير التحليل الذكي للسوق المصري EGX*\n\n"
            "📈 *الاستراتيجية: التوقعات المستقبلية (شهر + شهرين)*\n"
            "🎯 *الهدف: اختيار السهم + توقيت الدخول*\n"
            "☪️ *بعد فلتر التوافق الشرعي والسيولة*\n\n"
        )


        # ==========================================================
        # Process Opportunities
        # ==========================================================

        for item in opportunities:

            ticker = item.get(
                "ticker",
                item.get(
                    "symbol",
                    "N/A"
                )
            )

            score = int(
                item.get(
                    "score",
                    0
                )
            )


            # ======================================================
            # Current Price
            # ======================================================

            price = float(
                item.get(
                    "current_market_price",
                    item.get(
                        "price",
                        0
                    )
                )
            )

            historical_close = float(
                item.get(
                    "historical_close",
                    0
                )
            )

            price_status = item.get(
                "price_status",
                "غير متوفر"
            )

            price_source = item.get(
                "price_source",
                "غير متوفر"
            )

            market_datetime = item.get(
                "market_datetime",
                "غير متوفر"
            )


            # ======================================================
            # Trend & Forecasts
            # ======================================================

            trend_status = item.get(
                "trend_status",
                "غير متوفر"
            )

            forecast_1m_score = int(
                item.get(
                    "forecast_1m_score",
                    0
                )
            )

            forecast_2m_score = int(
                item.get(
                    "forecast_2m_score",
                    0
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

            ma200_slope = float(
                item.get(
                    "ma200_slope",
                    0
                )
            )

            ema50_slope = float(
                item.get(
                    "ema50_slope",
                    0
                )
            )


            # ======================================================
            # Entry
            # ======================================================

            entry_status = item.get(
                "entry_status",
                "غير متوفر"
            )

            ideal_entry = float(
                item.get(
                    "ideal_entry",
                    price
                )
            )

            entry_high = float(
                item.get(
                    "entry_high",
                    price
                )
            )

            distance_from_ema = float(
                item.get(
                    "distance_from_ema",
                    0
                )
            )


            # ======================================================
            # Risk Management
            # ======================================================

            shares = int(
                item.get(
                    "shares",
                    0
                )
            )

            stop_loss = float(
                item.get(
                    "stop_loss",
                    0
                )
            )

            stop_loss_pct = float(
                item.get(
                    "stop_loss_pct",
                    0
                )
            )

            tp1 = float(
                item.get(
                    "tp1",
                    0
                )
            )

            tp2 = float(
                item.get(
                    "tp2",
                    0
                )
            )

            position_value = float(
                item.get(
                    "position_value",
                    0
                )
            )

            actual_risk = float(
                item.get(
                    "actual_risk",
                    0
                )
            )

            risk_per_share = float(
                item.get(
                    "risk_per_share",
                    0
                )
            )

            rr1 = float(
                item.get(
                    "rr1",
                    0
                )
            )

            rr2 = float(
                item.get(
                    "rr2",
                    0
                )
            )


            # ======================================================
            # Technical Data
            # ======================================================

            volume_ratio = float(
                item.get(
                    "volume_ratio",
                    0
                )
            )

            support = float(
                item.get(
                    "support",
                    0
                )
            )

            resistance = float(
                item.get(
                    "resistance",
                    0
                )
            )

            atr = float(
                item.get(
                    "atr",
                    0
                )
            )


            # ======================================================
            # Recommendation
            # ======================================================

            recommendation = item.get(
                "rec",
                "🟡 WATCH"
            )


            # ======================================================
            # Entry Interpretation
            # ======================================================

            if entry_status.startswith("🟢"):

                entry_message = (
                    "🟢 *الدخول مناسب حالياً*"
                )

            elif entry_status.startswith("🟡"):

                entry_message = (
                    "🟡 *انتظر نقطة دخول أفضل*"
                )

            else:

                entry_message = (
                    "🔴 *لا يوجد دخول حالياً*"
                )


            # ======================================================
            # Score Interpretation
            # ======================================================

            if score >= 90:

                score_message = (
                    "🔥 تقييم استثنائي"
                )

            elif score >= 85:

                score_message = (
                    "🟢 تقييم قوي"
                )

            elif score >= 75:

                score_message = (
                    "🟡 تقييم جيد"
                )

            else:

                score_message = (
                    "⚪ تقييم ضعيف"
                )


            # ======================================================
            # Price Freshness Interpretation
            # ======================================================

            if price_status == "fresh":

                freshness_message = (
                    "🟢 *السعر حديث*"
                )

            elif price_status == "stale_session":

                freshness_message = (
                    "🔴 *السعر من جلسة سابقة*"
                )

            else:

                freshness_message = (
                    "🟡 *حالة السعر غير مؤكدة*"
                )


            # ======================================================
            # Stock Message
            # ======================================================

            stock_message = (

                f"📌 *السهم:* `{ticker}`\n"

                f"⭐ *Score:* `{score}/100`\n"

                f"📊 *تقييم النظام:* "
                f"{score_message}\n"

                f"🎯 *التوصية:* "
                f"{recommendation}\n\n"


                # --------------------------------------------------
                # Future Forecasts
                # --------------------------------------------------

                f"📈 *التوقعات المستقبلية:*\n"

                f"• الشهر القادم: "
                f"`{forecast_1m_score}/100`\n"

                f"  {forecast_1m_status}\n"

                f"• الشهرين القادمين: "
                f"`{forecast_2m_score}/100`\n"

                f"  {forecast_2m_status}\n"

                f"• الحالة العامة: "
                f"{trend_status}\n\n"


                # --------------------------------------------------
                # Current Market Price
                # --------------------------------------------------

                f"💵 *السعر الحالي:* "
                f"`{price:.2f}` ج.م\n"

                f"📅 *آخر إغلاق يومي:* "
                f"`{historical_close:.2f}` ج.م\n"

                f"🕐 *آخر تحديث للسعر:* "
                f"`{market_datetime}`\n"

                f"📡 *مصدر السعر:* "
                f"`{price_source}`\n"

                f"{freshness_message}\n\n"


                # --------------------------------------------------
                # Entry
                # --------------------------------------------------

                f"🎯 *منطقة الدخول المقترحة:*\n"

                f"`{ideal_entry:.2f} - "
                f"{entry_high:.2f}` ج.م\n"

                f"📊 *حالة الدخول:* "
                f"{entry_status}\n"

                f"{entry_message}\n"

                f"📏 *البعد عن EMA20:* "
                f"`{distance_from_ema:+.1f}%`\n\n"


                # --------------------------------------------------
                # Trend Indicators
                # --------------------------------------------------

                f"📊 *المؤشرات الرئيسية:*\n"

                f"• MA200 Slope: "
                f"`{ma200_slope:+.2f}%`\n"

                f"• EMA50 Slope: "
                f"`{ema50_slope:+.2f}%`\n"

                f"• Volume: "
                f"`{volume_ratio:.2f}x`\n"

                f"• ATR: "
                f"`{atr:.2f}`\n\n"


                # --------------------------------------------------
                # Risk Management
                # --------------------------------------------------

                f"🛑 *Stop Loss:* "
                f"`{stop_loss:.2f}` ج.م\n"

                f"📉 *نسبة وقف الخسارة:* "
                f"`{stop_loss_pct:.2f}%`\n"

                f"⚠️ *المخاطرة للسهم:* "
                f"`{risk_per_share:.2f}` ج.م\n\n"


                # --------------------------------------------------
                # Position
                # --------------------------------------------------

                f"📦 *الكمية المقترحة:* "
                f"`{shares:,}` سهم\n"

                f"💰 *قيمة الصفقة:* "
                f"`{position_value:,.2f}` ج.م\n"

                f"⚠️ *المخاطرة الفعلية:* "
                f"`{actual_risk:,.2f}` ج.م\n\n"


                # --------------------------------------------------
                # Targets
                # --------------------------------------------------

                f"🎯 *الهدف الأول TP1:* "
                f"`{tp1:.2f}` ج.م\n"

                f"📈 *Risk / Reward:* "
                f"`1:{rr1:.2f}`\n\n"

                f"🎯 *الهدف الثاني TP2:* "
                f"`{tp2:.2f}` ج.م\n"

                f"📈 *Risk / Reward:* "
                f"`1:{rr2:.2f}`\n\n"


                # --------------------------------------------------
                # Support / Resistance
                # --------------------------------------------------

                f"📍 *الدعم:* "
                f"`{support:.2f}` ج.م\n"

                f"🚧 *المقاومة:* "
                f"`{resistance:.2f}` ج.م\n\n"


                # --------------------------------------------------
                # Reasons
                # --------------------------------------------------

                f"💡 *أسباب التقييم:*\n"
            )


            # ======================================================
            # Reasons
            # ======================================================

            reasons = item.get(
                "reasons",
                []
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


            # ======================================================
            # Telegram Message Limit
            # ======================================================

            if len(
                current_message +
                stock_message
            ) > 3800:

                messages.append(
                    current_message
                )

                current_message = (
                    "🏆 *تكملة تقرير السوق المصري EGX*\n\n"
                    +
                    stock_message
                )

            else:

                current_message += (
                    stock_message
                )


        # ==========================================================
        # Add Final Message
        # ==========================================================

        if current_message.strip():

            messages.append(
                current_message
            )


        # ==========================================================
        # Send Messages
        # ==========================================================

        for message in messages:

            bot.send_message(
                ADMIN_CHAT_ID,
                message,
                parse_mode="Markdown"
            )


        print(
            "✅ تم إرسال تقرير التحليل "
            "والتوقعات والدخول وإدارة المخاطر بنجاح."
        )


    except Exception as e:

        print(
            f"❌ Error sending report: {e}"
                )
