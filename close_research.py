"""UI-only dated close research. Never a strategy input or trade recommendation."""
import numpy as np
import pandas as pd


def build_close_research(payload, symbol, now):
    try:
        from config import TIMEZONE_NAME
        r=payload['chart']['result'][0];m=r['meta'];ts=r['timestamp'];q=r['indicators']['quote'][0]
        if not (m.get('symbol')==symbol and m.get('currency')=='EGP'
                and m.get('exchangeName') in ('CAI','EGX')
                and m.get('exchangeTimezoneName')==TIMEZONE_NAME and m.get('dataGranularity')=='1d'):
            return None
        if not isinstance(ts,list) or not ts or any(isinstance(t,bool) or not isinstance(t,(int,float)) or not np.isfinite(t) for t in ts):return None
        if any(b<=a for a,b in zip(ts,ts[1:])):return None
        if any(not isinstance(q.get(k),list) or len(q[k])!=len(ts) for k in ('open','high','low','close','volume')):return None
        dates=pd.to_datetime(ts,unit='s',utc=True).tz_convert(TIMEZONE_NAME).tz_localize(None).normalize()
        if dates.has_duplicates or dates[-1].date()>now.date():return None
        # Always exclude today's potentially unfinished session in this historical-only mode.
        past=dates.date<now.date();dates=dates[past]
        close=pd.to_numeric(pd.Series(q['close']),errors='coerce')[past].to_numpy(dtype=float)
        missing=np.isnan(close)
        # Null provider rows are reported, not invented. Non-null malformed values reject.
        raw=np.array(q['close'],dtype=object)[past]
        if any(v is not None for v in raw[missing]):return None
        if any(isinstance(v,bool) for v in raw):return None
        if any(not np.isfinite(v) or v<=0 for v in close[~missing]):return None
        good=pd.DataFrame({'Close':close},index=dates)
        gaps=[d.date().isoformat() for d in dates[missing]]
        good=good.loc[~missing].copy()
        if len(good)<2:return None
        good['EMA20']=good.Close.ewm(span=20,adjust=False,min_periods=20).mean()
        good['EMA50']=good.Close.ewm(span=50,adjust=False,min_periods=50).mean()
        good['MA200']=good.Close.rolling(200,min_periods=200).mean()
        delta=good.Close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
        rsi=100-100/(1+gain/loss.replace(0,np.nan))
        rsi=rsi.mask((loss==0)&(gain>0),100).mask((gain==0)&(loss>0),0)
        good['RSI14']=rsi
        good.attrs.update(mode='close_research',history_as_of=good.index[-1].date().isoformat(),
                          gap_dates=gaps,instrument_type=str(m.get('instrumentType','unknown')),
                          retrieved_at=now.isoformat(),age_days=(now.date()-good.index[-1].date()).days)
        return good
    except (KeyError,TypeError,ValueError,IndexError,OverflowError):return None


def render_close_research(st, df, symbol):
    import plotly.graph_objects as go
    st.markdown("""<style>
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
    [data-testid="stCaptionContainer"] {color:#e2e8f0 !important;}
    [data-testid="stAlert"], [data-testid="stAlertContainer"] {background:#172333 !important; color:#f1f5f9 !important;}
    [data-testid="stAlert"] p {color:#f1f5f9 !important;}
    .block-container {padding-top:5rem !important;}
    </style>""", unsafe_allow_html=True)
    st.subheader('عرض تاريخي محدود | '+symbol)
    st.warning('التحليل الكامل غير متاح. هذا عرض إغلاق يومي فقط، وليس توصية شراء أو بيع أو سعرًا داخل الجلسة.')
    st.caption('Yahoo Finance | EGP | آخر إغلاق: '+df.attrs['history_as_of']+' | عمر آخر إغلاق بالأيام: '+str(df.attrs['age_days']))
    st.info('أسعار المصدر لم تُراجع بشكل مستقل. لم تجتز البيانات فحوص التحليل الكامل؛ لا نعتبر الإغلاق مؤكدًا من البورصة. لم نغيّر الأسعار ولم نفترض أن الفتح هو إغلاق أمس. لا توجد شموع أو أهداف أو وقف خسارة أو درجة ثقة هنا.')
    gaps=df.attrs['gap_dates']
    st.warning('الحسابات على الإغلاقات المتاحة فقط، وليست جلسات متصلة مؤكدة. صفوف إغلاق مفقودة: '+str(len(gaps))+(' | التواريخ: '+', '.join(gaps) if gaps else '')+'. لم نتحقق من تقويم السوق، وقد توجد تواريخ غائبة أخرى. لا تعويض للأسعار المفقودة.')
    st.caption('وصف الأداة من Yahoo: '+df.attrs['instrument_type']+' | إغلاقات متاحة: '+str(len(df))+' | ليست عائدًا كليًا معدلًا بالتوزيعات. لا إثبات لأداء استراتيجية.')
    cols=st.columns(5);last=df.iloc[-1]
    for col,key,label in zip(cols,['Close','EMA20','EMA50','MA200','RSI14'],['Close EGP','EMA20 EGP','EMA50 EGP','MA200 EGP','RSI14']):
        value=last[key];col.metric(label,'غير متاح' if pd.isna(value) else f'{value:.2f}')
    st.caption('EMA20/50 وMA200: عدد الإغلاقات المتاحة. RSI14: تسوية Wilder على الإغلاقات المتاحة؛ القيم غير الكافية لا تُعرض.')
    fig=go.Figure(go.Scatter(x=df.index,y=df.Close,name='Close EGP',mode='lines'))
    for key in ['EMA20','EMA50','MA200']:fig.add_trace(go.Scatter(x=df.index,y=df[key],name=key,mode='lines'))
    fig.update_layout(height=360,template='plotly_dark',yaxis_title='EGP',xaxis_title='Available daily closes',margin=dict(l=20,r=20,t=20,b=40))
    st.plotly_chart(fig,use_container_width=True)
    st.caption('الخط يصل المشاهدات المتاحة ولا يثبت اكتمال البيانات بين التواريخ. العرض التاريخي لا يعيد تشغيل التحليل الكامل أو التقارير التلقائية.')
