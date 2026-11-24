"""Organized dated dashboard. Technical context only, no private holdings."""
import html
import pandas as pd


def render_dashboard(st,frame,symbol):
    import plotly.graph_objects as go
    from daily_research import research_record
    from telegram_presentation import technical_card
    item=research_record(symbol,frame)
    def n(key):return 'غير متاح' if item.get(key) is None else f"{item[key]:,.2f}"
    st.markdown('''<style>
    .lr-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;direction:rtl;margin:18px 0}
    .lr-card{background:#101820;border:1px solid #263441;border-radius:16px;padding:18px;color:#e7edf2;min-width:0}
    .lr-label{font-size:14px;color:#a6b7c7;margin-bottom:10px}.lr-value{font:700 28px Arial;color:#f1f6fa;direction:ltr;text-align:right;overflow-wrap:anywhere}
    .lr-small{font-size:13px;line-height:1.7;color:#a6b7c7;margin-top:8px}.lr-hero{display:flex;justify-content:space-between;gap:20px;direction:rtl;align-items:center;padding:24px;background:#101820;border:1px solid #263441;border-radius:18px;margin:14px 0}
    .lr-title{font:700 26px Arial;color:#f1f6fa}.lr-prose{direction:rtl;text-align:right;line-height:1.9;color:#e7edf2;overflow-wrap:anywhere}
    @media(max-width:650px){.lr-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.lr-card{padding:14px}.lr-value{font-size:23px}.lr-hero{padding:18px}.block-container{padding-left:16px!important;padding-right:16px!important}}
    </style>''',unsafe_allow_html=True)
    st.caption('لوحة يومية مؤرخة | dashboard-r7 | Yahoo Finance | '+item['history_as_of'])
    st.markdown('<div class="lr-hero"><div><div class="lr-title">'+html.escape(symbol)+'</div><div class="lr-small">جلسة '+item['history_as_of']+' · جنيه مصري · ليست أسعارًا لحظية</div></div><div><div class="lr-label">آخر إغلاق</div><div class="lr-value">'+n('Close')+'</div></div></div>',unsafe_allow_html=True)
    cards=[('متوسط20','EMA20','متوسط الإغلاقات القريبة'),('متوسط50','EMA50','مرجع الاتجاه المتوسط'),('قوة الحركة','RSI14','مقياس من0إلى100، ليس احتمال نجاح'),('حجم التداول','Volume_Ratio','مقارنة بمتوسط الحجم، مرة'),('الدعم السابق','Support_20','قاع20مشاهدة سابقة'),('المقاومة السابقة','Resistance_20','قمة20مشاهدة سابقة'),('تذبذب السعر','ATR_14','متوسط مدى الحركة، جنيه'),('التقييم الإجمالي',None,'غير متاح، لا نجمع مدخلات ناقصة')]
    st.markdown('<div class="lr-grid">'+''.join('<div class="lr-card"><div class="lr-label">'+title+'</div><div class="lr-value">'+(n(key) if key else 'غير متاح')+'</div><div class="lr-small">'+desc+'</div></div>' for title,key,desc in cards)+'</div>',unsafe_allow_html=True)
    st.subheader('الخلاصة: ما يدعم السهم وما يضعفه')
    text=technical_card(item)
    start=text.index('الخلاصة');end=text.index('🎯 سيناريو') if '🎯 سيناريو' in text else text.index('⚠️ إيه اللي ناقص')
    synopsis=text[start:end].strip()
    st.markdown('<div class="lr-card lr-prose">'+html.escape(synopsis).replace('\n','<br>')+'</div>',unsafe_allow_html=True)
    st.subheader('خريطة حركة السعر')
    chart=frame.tail(120)
    fig=go.Figure(go.Scatter(x=chart.index,y=chart.Close,name='الإغلاق',line=dict(color='#63a8ff',width=2.5)))
    for key,color in [('EMA20','#f6c86c'),('EMA50','#bd9aff'),('MA200','#7ac9a5')]:
        fig.add_trace(go.Scatter(x=chart.index,y=chart[key],name=key,line=dict(color=color,width=1.3)))
    for key,label,color in [('Support_20','دعم سابق','#57ca9e'),('Resistance_20','مقاومة سابقة','#ed7d82')]:
        if item.get(key) is not None:fig.add_hline(y=item[key],line_dash='dot',line_color=color,annotation_text=label)
    fig.update_layout(template='plotly_dark',height=420,margin=dict(l=12,r=12,t=28,b=25),legend=dict(orientation='h'),yaxis_title='جنيه مصري',paper_bgcolor='#0b1015',plot_bgcolor='#0b1015')
    st.plotly_chart(fig,use_container_width=True)
    st.caption('خط الإغلاق بدل شموع غير سليمة. الربط بين المشاهدات لا يثبت اتصال جلسات التداول.')
    st.subheader('مكونات القراءة الفنية')
    for comp in item['components']:
        label=comp['label'];score=comp['score'];maximum=comp['maximum']
        st.write(label+' · '+('غير متاح' if score is None else f'{score:g} من {maximum}'))
        if score is not None:st.progress(max(0.,min(1.,score/maximum)))
    st.info('لا رادار مكتمل أو احتمالات صعود مصطنعة. المكونات هنا منفصلة، والدرجة الإجمالية غير متاحة.')
    st.subheader('المستويات النظرية، ليست توقعات')
    levels=item.get('levels')
    if levels:
        st.markdown('<div class="lr-grid">'+''.join('<div class="lr-card"><div class="lr-label">'+label+'</div><div class="lr-value">'+f'{levels[key]:.2f}'+'</div></div>' for label,key in [('مرجع الحساب','reference'),('حد خسارة نظري','stop'),('مستوى أول','tp1'),('مستوى ثانٍ','tp2')])+'</div>',unsafe_allow_html=True)
        st.caption('الوقف محسوب من التذبذب والدعم، والمستويان2Rو3R. ليست أوامر أو أسعارًا متوقعة؛ التنفيذ قد يختلف مع الفجوات والتكاليف.')
    else:st.write('غير متاحة: المدخلات لا تكفي، ولا نضع نسبة افتراضية.')
    with st.expander('حدود البيانات والتفاصيل الفنية',expanded=False):
        st.write('سعر الفتح: '+n('selected_open')+'. لا نستخدم فتح يوم أقدم. أنماط تحتاج فتحًا غير سليم تظهر غير متاحة.')
        st.write('إغلاق مفقود: '+(', '.join(item['gap_dates']) or 'لا صفوف فارغة مرصودة')+'. الحساب على المشاهدات المتاحة فقط.')
        st.write('تقويم السوق وأسعار المصدر وأثر التوزيعات غير متحقق منها مستقلًا. وصف Yahoo: '+item['instrument_type']+'، غير معتمد هنا.')
        st.write('احتمال النجاح ومدة الهدف والمقارنة السوقية غير متاحة. لا إثبات لأداء استراتيجية أو عوائد مضمونة.')
        for label,key in [('MACD','MACD'),('إشارة MACD','MACD_Signal'),('قوة الاتجاه ADX','ADX_14'),('قياس ضغط التداول CMF','CMF_20'),('متوسط200','MA200')]:st.write(label+': '+n(key))
    st.caption('متابعة المحفظة الخاصة منفصلة، لا نعرض الكميات والتكلفة الشخصية على الصفحة المفتوحة. البحث والوصف فقط، لا توصية شخصية بتداول.')
