"""Capability-aware dated daily research, shared by the app and report formatter.
No portfolio ownership, personal sizing, calibrated probabilities, or live quotes.
"""
import math
import numpy as np
import pandas as pd


def finite(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def enrich_history(frame, quote, source_dates):
    from indicators import calculate_indicators
    out=frame.copy()
    for key in ('Open','High','Low','Volume'):
        raw=pd.Series(quote[key.lower()],index=source_dates).reindex(out.index)
        numeric=pd.to_numeric(raw,errors='coerce')
        valid=raw.map(lambda x:isinstance(x,(int,float)) and not isinstance(x,bool) and np.isfinite(x))
        valid &= numeric.ge(0) if key=='Volume' else numeric.gt(0)
        out[key]=numeric.where(valid)
    hlc=out[['High','Low','Close']].notna().all(axis=1)&(out.High>=out.Low)&(out.Close<=out.High+out.Close.abs()*1e-6)&(out.Close>=out.Low-out.Close.abs()*1e-6)
    open_ok=hlc&out.Open.notna()&(out.Open<=out.High+out.Close.abs()*1e-6)&(out.Open>=out.Low-out.Close.abs()*1e-6)
    out.loc[~open_ok,'Open']=np.nan
    out.attrs.update(hlcv_available=bool(hlc.all() and out.Volume.notna().all()),
                     invalid_hlc_rows=int((~hlc).sum()),invalid_open_rows=int((~open_ok).sum()))
    # A bad HLCV window must not leak partially-filled rolling values. Close
    # research remains available; enriched measures require the entire input run.
    if out.attrs['hlcv_available']:
        enriched=calculate_indicators(out,require_open=False)
        if enriched is not None:
            out=enriched
    return out


def research_record(symbol,frame):
    r=frame.iloc[-1];attrs=frame.attrs
    keys=('Close','EMA20','EMA50','MA200','RSI14','EMA_20','EMA_50','MA_200','RSI_14','MACD','MACD_Signal','MACD_Hist','ATR_14','ATR_Pct','ADX_14','PLUS_DI','MINUS_DI','Volume_Ratio','CMF_20','MFI_14','OBV_Slope_10D','Support_20','Resistance_20','Chandelier_22','Close_Location','Candle_Body_Pct','Upper_Shadow_Pct','Lower_Shadow_Pct','Gap_Pct')
    item={'ticker':symbol,'mode':'close_research','history_as_of':attrs['history_as_of'],'currency':'EGP','selected_open':attrs.get('selected_open'),'selected_bar_ohlc_consistent':attrs.get('selected_bar_ohlc_consistent',False),'gap_dates':attrs.get('gap_dates',[]),'instrument_type':attrs.get('instrument_type','unknown'),'observed_closes':len(frame),'hlcv_available':attrs.get('hlcv_available',False),'invalid_open_rows':attrs.get('invalid_open_rows',0),'retrieved_at':attrs.get('retrieved_at')}
    item.update({k:finite(r.get(k)) for k in keys})
    item['components']=[]
    if item['hlcv_available'] and finite(r.get('ATR_14')) is not None:
        from strategy import calculate_trend_score,calculate_momentum_score,calculate_volume_score,calculate_sr_score,calculate_money_flow_score,calculate_volatility_score,calculate_price_strength_score
        for label,fn,maximum in [('الاتجاه',calculate_trend_score,20),('الزخم',calculate_momentum_score,15),('الحجم',calculate_volume_score,15),('الدعم والمقاومة',calculate_sr_score,15),('تدفق الأموال',calculate_money_flow_score,10),('التذبذب',calculate_volatility_score,5),('القوة السعرية',calculate_price_strength_score,5)]:
            requirements={
                'الاتجاه':['Close','EMA_20','EMA_50','MA_200','EMA50_Slope_10D','MA200_Slope_20D','ADX_14','PLUS_DI','MINUS_DI'],
                'الزخم':['RSI_14','MACD','MACD_Signal','MACD_Hist','ROC_20D','ROC_60D'],
                'الحجم':['Volume_Ratio','Resistance_20'],
                'الدعم والمقاومة':['Support_20','Resistance_20','Distance_From_Support_Pct','Distance_From_Resistance_Pct'],
                'تدفق الأموال':['OBV_Slope_10D','CMF_20','MFI_14','AD_Slope_20D'],
                'التذبذب':['ATR_Pct','BB_POSITION'],
                'القوة السعرية':['Position_52W','Return_20D','Return_60D']}
            if any(finite(r.get(k)) is None for k in requirements[label]):
                item['components'].append({'label':label,'score':None,'maximum':maximum,'reasons':['مدخلات غير كافية، لا نحولها إلى صفر']})
                continue
            score,reasons=fn(r)
            # Existing wording assumes consecutive sessions. Report the window basis honestly.
            reasons=[x.replace('جلسة','مشاهدة').replace('مؤكد','حسابي') for x in reasons]
            item['components'].append({'label':label,'score':float(score),'maximum':maximum,'reasons':reasons})
    item['candles']={}
    for key in ('Hammer','Strong_Bullish_Candle','Bullish_Engulfing'):
        value=r.get(key)
        item['candles'][key]=None if pd.isna(value) else bool(value)
    item['levels']=None
    if item['hlcv_available'] and item['ATR_14'] and item['ATR_14']>0:
        from config import ATR_STOP_MULTIPLIER,SUPPORT_ATR_BUFFER,TP1_R_MULTIPLE,TP2_R_MULTIPLE
        c=item['Close'];atr=item['ATR_14'];support=item['Support_20']
        stop=c-ATR_STOP_MULTIPLIER*atr
        if support is not None and 0<support<c:stop=min(stop,support-SUPPORT_ATR_BUFFER*atr)
        if 0<stop<c:
            risk=c-stop
            item['levels']={'reference':c,'stop':stop,'tp1':c+TP1_R_MULTIPLE*risk,'tp2':c+TP2_R_MULTIPLE*risk,'r1':TP1_R_MULTIPLE,'r2':TP2_R_MULTIPLE,'atr_mult':ATR_STOP_MULTIPLIER,'support_buffer':SUPPORT_ATR_BUFFER}
    return item


def format_research(item):
    def n(key):
        v=item.get(key);return 'غير متاح' if v is None else f'{v:.2f}'
    def yes(v):return 'غير متاح' if v is None else ('متحقق حسابيًا' if v else 'غير متحقق حسابيًا')
    lines=[f"📌 {item['ticker']} | تقرير فني يومي | Yahoo Finance | EGP",f"📅 جلسة المصدر: {item['history_as_of']} | إغلاق: {n('Close')} | فتح نفس الجلسة: {n('selected_open')}",
           'ليست أسعارًا لحظية. لا نعتمد شمعة اليوم قبل إثبات اكتمالها. الفتح غير المتاح لا يُستبدل بيوم أقدم.',
           f"الأساس: {item['observed_closes']} مشاهدة متاحة. صفوف إغلاق فارغة: {', '.join(item['gap_dates']) or 'لا توجد صفوف فارغة مرصودة'}.",
           'النوافذ بعدد المشاهدات، وليست جلسات متصلة مؤكدة. لا تعويض للصفوف المفقودة، وتقويم السوق غير متحقق.',
           f"وصف الأداة من المصدر: {item['instrument_type']}؛ وصف غير معتمد هنا. الأسعار لم تُراجع مستقلًا، وأثر التوزيعات غير معتمد.",
           '\n📈 الاتجاه والزخم',f"EMA20 {n('EMA20')} | EMA50 {n('EMA50')} | MA200 {n('MA200')} | RSI14 {n('RSI14')}",
           f"MACD {n('MACD')} | Signal {n('MACD_Signal')} | Histogram {n('MACD_Hist')}",f"ADX {n('ADX_14')} | DI+ {n('PLUS_DI')} | DI- {n('MINUS_DI')}",
           '\n💧 الحجم وتدفق الأموال',f"حجم/متوسط20: {n('Volume_Ratio')} | CMF20 {n('CMF_20')} | MFI14 {n('MFI_14')}",
           '\n📍 الدعم والمقاومة والتذبذب',f"دعم20 {n('Support_20')} | مقاومة20 {n('Resistance_20')} | ATR14 {n('ATR_14')} ({n('ATR_Pct')}%)",f"Chandelier22 النظري: {n('Chandelier_22')}",
           '\n🕯 الشموع',f"Hammer: {yes(item['candles'].get('Hammer'))} | Engulfing: {yes(item['candles'].get('Bullish_Engulfing'))}",f"شمعة صاعدة قوية: {yes(item['candles'].get('Strong_Bullish_Candle'))} | موضع الإغلاق HLC: {n('Close_Location')}",
           'أي نمط يحتاج فتحًا غير متسق في نافذته يظهر غير متاح، لا إشارة سلبية مفترضة.',
           '\n⭐ التقييم والأسباب','الدرجة المركبة /100: غير متاحة. لا إعادة تطبيع للأجزاء ولا ترتيب فرص على أساسها.']
    for comp in item['components']:
        lines.append(f"{comp['label']}: "+("غير متاح" if comp['score'] is None else f"{comp['score']:g}/{comp['maximum']}")+(' | '+'؛ '.join(comp['reasons']) if comp['reasons'] else ''))
    if not item['components']:lines.append('مكونات HLCV غير متاحة: سجل غير كافٍ أو مدخلات غير متسقة.')
    lines+=['\n⏱ المضاربة والأيام/الأسابيع','قراءة جلسة سابقة فقط، لا تنفيذ داخل الجلسة. الاتجاه والزخم أعلاه يصلحان للوصف اليومي، لا يثبتان أفضلية تداول.',
            'تأكيد pullback غير متاح إذا فشل الفتح. المقارنة السوقية وترتيب القوة النسبية غير متاحين هنا دون كون أسهم موحد التاريخ.',
            'إشارة تداول معتمدة / احتمال نجاح / مدة وصول للهدف: غير متاح، لا يوجد نموذج أداء متحقق لهذه البيانات.',
            '\n🎯 الدخول والوقف والأهداف النظرية']
    levels=item['levels']
    if levels:
        lines +=[f"مرجع الحساب = الإغلاق {levels['reference']:.2f}، وليس أمر دخول أو نطاق شراء.",f"وقف نظري {levels['stop']:.2f} | TP1 {levels['tp1']:.2f} ({levels['r1']:g}R) | TP2 {levels['tp2']:.2f} ({levels['r2']:g}R)",f"الصيغة المحفوظة: الأوسع بين الإغلاق ناقص {levels['atr_mult']:g}×ATR والدعم ناقص {levels['support_buffer']:g}×ATR عندما يكون الدعم دون الإغلاق؛ R هو بُعد المرجع عن الوقف.",'هذه مستويات سيناريو حسابي وليست أهدافًا متوقعة أو توصية، ولا تتضمن تكلفة التنفيذ أو الانزلاق.']
    else:lines.append('غير متاح: مدخلات HLCV/فترة الحساب لا تكفي، ولا نضع وقفًا افتراضيًا بنسبة ثابتة.')
    lines+=['\n📦 حجم الصفقة وإدارة المال','غير متاح: رأس المال ونسبة المخاطرة غير مؤكدين. لا نستخدم القيم الافتراضية كأموال المستخدم.',
            '\n💼 متابعة المحفظة','متابعة المحفظة الخاصة تُجهز منفصلة وفق الأساس الذي اختاره المستخدم. لا تعرض الصفحة المفتوحة الكميات أو أسعار الشراء أو الربح/الخسارة.',
            '\nللبحث والوصف فقط، وليس نصيحة استثمارية. لا توجد عوائد مضمونة.']
    return '\n'.join(lines)+'\n\n'


def render_research(st,frame,symbol):
    import plotly.graph_objects as go
    import html
    item=research_record(symbol,frame)
    st.subheader('التقرير الفني اليومي | '+symbol)
    st.caption('نسخة dated-full-r5 | جلسة المصدر: '+item['history_as_of'])
    st.warning('Yahoo Finance، جلسة سابقة مؤرخة، ليست أسعارًا لحظية. أجزاء التقرير غير المتاحة موضحة في مكانها.')
    for section in format_research(item).strip().split('\n\n'):
        rows=section.split('\n')
        if len(rows)>1:
            st.markdown('#### '+rows[0])
            st.markdown('<div dir="rtl" style="text-align:right;line-height:1.9;overflow-wrap:anywhere">'+'<br>'.join(html.escape(row) for row in rows[1:])+'</div>',unsafe_allow_html=True)
        else:st.write(section)
    fig=go.Figure(go.Scatter(x=frame.index,y=frame.Close,name='Close EGP'))
    for key in ('EMA20','EMA50','MA200'):fig.add_trace(go.Scatter(x=frame.index,y=frame[key],name=key))
    fig.update_layout(height=360,template='plotly_dark',yaxis_title='EGP',margin=dict(l=10,r=10,t=20,b=30))
    st.plotly_chart(fig,use_container_width=True)
    st.caption('الخط يصل المشاهدات المتاحة، ولا يثبت اتصال الجلسات. التقرير النصي أعلاه هو نفس محتوى معاينة Telegram، ولا يرسل تلقائيًا من الصفحة.')
