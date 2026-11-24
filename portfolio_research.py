"""Dated portfolio arithmetic from an explicitly selected stored holdings basis.
Private report only. Never render personal quantities/costs on the open app.
"""
from decimal import Decimal, ROUND_HALF_UP
import math


def money(value):
    return format(Decimal(str(value)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),',.2f')


def build_portfolio_snapshot(holdings, frames):
    rows=[]
    for ticker,holding in holdings.items():
        shares=holding.get('shares');buy=holding.get('buy_price')
        if isinstance(shares,bool) or not isinstance(shares,int) or shares<=0:
            raise ValueError('Invalid stored share count')
        buy=Decimal(str(buy))
        if not buy.is_finite() or buy<=0:raise ValueError('Invalid stored purchase basis')
        cost=buy*shares
        row={'ticker':ticker,'shares':shares,'buy_price':str(buy),'cost':str(cost),'date':None,'close':None,'value':None,'pnl':None,'pnl_pct':None,'technical':None}
        frame=frames.get(ticker) if ticker in frames else frames.get(ticker+'.CA')
        if frame is not None and not frame.empty:
            from daily_research import research_record
            close=float(frame.iloc[-1]['Close'])
            if math.isfinite(close) and close>0:
                price=Decimal(str(close));value=price*shares;pnl=value-cost
                row.update(date=frame.attrs['history_as_of'],close=str(price),value=str(value),pnl=str(pnl),pnl_pct=str(pnl/cost*100),technical=research_record(ticker+'.CA',frame))
        rows.append(row)
    valued=[r for r in rows if r['close'] is not None]
    dates=sorted({r['date'] for r in valued})
    same_date=len(dates)==1
    complete=len(valued)==len(rows) and same_date
    return {'rows':rows,'count':len(rows),'valued_count':len(valued),'dates':dates,'same_date':same_date,'complete':complete,
            'total_stored_cost':str(sum((Decimal(r['cost']) for r in rows),Decimal(0))),
            'covered_cost':str(sum((Decimal(r['cost']) for r in valued),Decimal(0))),
            'covered_value':str(sum((Decimal(r['value']) for r in valued),Decimal(0))) if same_date else None,
            'covered_pnl':str(sum((Decimal(r['pnl']) for r in valued),Decimal(0))) if same_date else None}


def format_private_portfolio(snapshot):
    blocks=[]
    for r in snapshot['rows']:
        lines=[f"💼 {r['ticker']} | متابعة المحفظة الخاصة",f"جلسة السعر: {r['date'] or 'غير متاحة'} | Yahoo Finance | EGP",
               f"الكمية {r['shares']:,} | متوسط الشراء المحفوظ {r['buy_price']} | التكلفة {money(r['cost'])}"]
        if r['close'] is None:
            lines+=['السعر والتقييم والربح/الخسارة: غير متاح. لا نعوض السعر بسعر الشراء أو بسهم آخر.']
        else:
            lines +=[f"إغلاق المصدر {money(r['close'])} | القيمة {money(r['value'])}",f"فرق سعري حسابي غير محقق {money(r['pnl'])} ج.م ({money(r['pnl_pct'])}%)"]
            t=r['technical']
            def n(k):return 'غير متاح' if t.get(k) is None else money(t[k])
            lines +=[f"EMA20 {n('EMA20')} | MA200 {n('MA200')} | RSI14 {n('RSI14')}",f"دعم20 {n('Support_20')} | مقاومة20 {n('Resistance_20')} | ATR14 {n('ATR_14')}",f"Chandelier22 النظري {n('Chandelier_22')}، مستوى حسابي لا أمر بيع.",
                      f"فتح نفس الجلسة {n('selected_open')} | الدرجة المركبة واحتمال النجاح ومدة الهدف: غير متاح.",
                      'صفوف إغلاق فارغة مرصودة: '+(', '.join(t['gap_dates']) or 'لا توجد صفوف فارغة مرصودة')+'.']
        lines+=['الأساس: آخر كميات وأسعار شراء محفوظة في الكود، باختيارك. ليست مزامنة مع حساب الوسيط.',
                'الأسعار مؤرخة وليست لحظية؛ النوافذ بالمشاهدات المتاحة، لا جلسات متصلة مؤكدة. تقويم السوق وأثر التوزيعات غير معتمدين.',
                'الفرق السعري لا يصح كعائد استثماري معتمد قبل مطابقة أي تجزئة أو زيادة رأس مال أو توزيع مع عدد الأسهم وتكلفة الشراء. لا يشمل عمولات/ضرائب/توزيعات/تكلفة خروج. لا توصية شخصية بالشراء أو البيع أو الاحتفاظ.']
        blocks.append('\n'.join(lines)+'\n\n')
    lines=['📊 ملخص المحفظة الخاصة','أساس الملكية: آخر تحديث محفوظ في portfolio.py باختيار المستخدم، وليس صورة التقرير القديمة.',
           f"مراكز محفوظة {snapshot['count']} | مراكز لها إغلاق صالح {snapshot['valued_count']} | تواريخ السعر: {', '.join(snapshot['dates']) or 'غير متاحة'}",
           f"إجمالي تكلفة الكميات المحفوظة: {money(snapshot['total_stored_cost'])} ج.م"]
    if snapshot['covered_value'] is not None:
        label='كامل المحفظة' if snapshot['complete'] else 'الجزء المسعّر فقط، ليس إجمالي المحفظة'
        pnl=Decimal(snapshot['covered_pnl']);cost=Decimal(snapshot['covered_cost'])
        lines +=[label,f"تكلفة الجزء المسعّر {money(cost)} | قيمته {money(snapshot['covered_value'])}",f"فرق سعري حسابي للجزء المسعّر {money(pnl)} ج.م ({money(pnl/cost*100)}%)"]
    else:lines.append('القيمة والربح/الخسارة المجمّعان غير متاحين: لا إغلاقات صالحة موحدة التاريخ.')
    if not snapshot['complete']:lines.append('إجمالي القيمة والربح/الخسارة لكامل المحفظة غير متاح؛ لا نحتسب المركز الناقص بصفر.')
    lines+=['حجم صفقة جديدة: غير متاح. اختيار المحفظة المحفوظة لا يثبت رأس مال كليًا أو نسبة مخاطرة للشراء.',
            'تقرير حسابي خاص للمراجعة، ليس مزامنة وسيط أو نصيحة استثمارية. لم يُرسل إلى Telegram.']
    blocks.append('\n'.join(lines)+'\n\n')
    from report import _chunk
    return _chunk(blocks,'متابعة خاصة وفق آخر تحديث محفظة محفوظ في الكود\n\n')
