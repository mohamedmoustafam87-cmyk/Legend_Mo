import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import EGX_STOCKS
from scanner import get_stock_data, fetch_mubasher_prices
from indicators import calculate_indicators
from strategy import evaluate_stock_strategy

# إعدادات صفحة الويب
st.set_page_config(
    page_title="EGX Smart Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 لوحة تحليل الأسهم المصرية (EGX Smart Dashboard)")
st.markdown("موقعك الخاص لمتابعة الشموع اليابانية، المؤشرات الفنية، مستويات الدعم والمقاومة، وإدارة المخاطر لأي سهم لحظياً.")

# زر جلب الأسعار اللحظية من مباشر
@st.cache_data(ttl=300)
def load_mubasher():
    return fetch_mubasher_prices()

mubasher_prices = load_mubasher()

# صندوق البحث لاختيار السهم
selected_stock = st.selectbox(
    "🔎 اختر أو ابحث عن السهم:",
    options=EGX_STOCKS,
    index=0
)

if selected_stock:
    with st.spinner(f"جاري جلب وتحليل بيانات السهم {selected_stock}..."):
        df = get_stock_data(selected_stock, mubasher_prices)
        
        if df is None or df.empty:
            st.error(f"⚠️ تعذر جلب بيانات كافية للسهم {selected_stock}")
        else:
            df = calculate_indicators(df)
            analysis = evaluate_stock_strategy(df, selected_stock)
            
            if analysis is None:
                st.warning("⚠️ لا توجد بيانات كافية لحساب مؤشرات هذا السهم.")
            else:
                # عرض البطاقات الإحصائية (Metrics)
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("السعر الحالي", f"{analysis['price']:.2f} ج.م")
                with col2:
                    st.metric("التقييم (Score)", f"{analysis['score']} / 100", analysis['rec'])
                with col3:
                    st.metric("مؤشر RSI", f"{df.iloc[-1]['RSI_14']:.1f}")
                with col4:
                    st.metric("مستويات الدعم", f"{analysis['support']:.2f} ج.م")

                st.markdown("---")

                # رسم الشموع اليابانية التفاعلية باستخدام Plotly
                st.subheader(f"📊 الرسم البياني والشموع اليابانية لـ {selected_stock}")
                
                recent_df = df.tail(120)  # آخر 120 جلسة
                
                fig = go.Figure(data=[go.Candlestick(
                    x=recent_df.index,
                    open=recent_df['Open'],
                    high=recent_df['High'],
                    low=recent_df['Low'],
                    close=recent_df['Close'],
                    name="الشموع اليابانية"
                )])
                
                # إضافة خطوط المتوسطات المتحركة EMA20 و MA200
                if 'EMA_20' in recent_df.columns:
                    fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['EMA_20'], mode='lines', name='EMA 20', line=dict(color='orange', width=1.5)))
                if 'MA_200' in recent_df.columns:
                    fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['MA_200'], mode='lines', name='MA 200', line=dict(color='blue', width=1.5)))

                fig.update_layout(
                    title=f"حركة السعر لـ {selected_stock}",
                    xaxis_title="التاريخ",
                    yaxis_title="السعر (ج.م)",
                    template="plotly_dark",
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)

                # تفاصيل المخاطر والأهداف
                st.markdown("---")
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.subheader("🎯 التوصيات والأهداف")
                    st.info(f"**منطقة الدخول المقترحة:** {analysis['ideal_entry']} - {analysis['entry_high']} ج.م")
                    st.success(f"**الهدف الأول (TP1):** {analysis['tp1']} ج.م (المدة: {analysis['days_tp1_text']})")
                    st.success(f"**الهدف الثاني (TP2):** {analysis['tp2']} ج.م (المدة: {analysis['days_tp2_text']})")
                
                with col_b:
                    st.subheader("🛑 إدارة المخاطر والخروج")
                    st.warning(f"**وقف الخسارة (Stop Loss):** {analysis['stop_loss']} ج.م ({analysis['stop_loss_pct']:.2f}%)")
                    st.error(f"**خطة الخروج:** {analysis['exit_strategy']}")

                # الأسباب الفنية
                st.subheader("💡 الأسباب والتحليل الفني:")
                for reason in analysis.get('reasons', []):
                    st.write(f"- {reason}")
