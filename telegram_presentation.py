"""Compact plain-text Telegram presentation. Does not change app or data."""
LRI='\u2066'
PDI='\u2069'


def value(v,digits=2):
    return 'غير متاح' if v is None else LRI+f'{float(v):,.{digits}f}'+PDI


def metric(label,v,suffix=''):
    return label+'  '+value(v)+((' '+suffix) if suffix else '')


def technical_card(item):
    c=item['Close'];e20=item.get('EMA20');e50=item.get('EMA50');ma=item.get('MA200');rsi=item.get('RSI14');hist=item.get('MACD_Hist')
    if all(v is not None for v in (c,e20,e50,ma)):
        if c>e20>e50 and c>ma:trend='السعر فوق متوسطاته، والاتجاه العام صاعد.'
        elif c<e20<e50 and c<ma:trend='السعر تحت متوسطاته، والاتجاه العام ضعيف.'
        else:trend='الاتجاه مختلط، المتوسطات لا تؤكد اتجاهًا واحدًا.'
    else:trend='البيانات لا تكفي لوصف الاتجاه.'
    if rsi is None or hist is None:momentum='البيانات لا تكفي لوصف قوة الحركة.'
    elif rsi>70:momentum='الحركة قوية لأعلى، لكن مؤشر القوة مرتفع. ده مش ضمان لاستمرار الصعود.'
    elif rsi<30:momentum='الحركة ضعيفة لأسفل. ده وحده مش دليل على ارتداد قريب.'
    elif rsi>50 and hist>0:momentum='الحركة تميل للإيجابية، من غير تأكيد لحركة قادمة.'
    elif rsi<50 and hist<0:momentum='الحركة تميل للضعف.'
    else:momentum='قوة الحركة متوازنة أو متضاربة، مفيش حسم.'
    vr=item.get('Volume_Ratio');flow=item.get('CMF_20')
    volume='حجم التداول غير متاح.' if vr is None else ('التداول أعلى من متوسطه.' if vr>=1.5 else ('التداول أقل من متوسطه.' if vr<.8 else 'التداول قريب من متوسطه.'))
    flow_text='قياس ضغط الشراء والبيع غير متاح.' if flow is None else ('قياس السيولة يميل لضغط شراء.' if flow>0 else ('قياس السيولة يميل لضغط بيع.' if flow<0 else 'قياس السيولة متوازن.'))
    support=item.get('Support_20');resistance=item.get('Resistance_20');adx=item.get('ADX_14')
    supporting=[];weakening=[]
    if ma is not None:(supporting if c>ma else weakening).append('الإغلاق '+('فوق' if c>ma else 'تحت')+' متوسط الاتجاه الطويل '+value(ma)+' جنيه.')
    if hist is not None:(supporting if hist>0 else weakening).append('فرق قياس الزخم '+value(hist)+'، '+('إيجابي.' if hist>0 else 'سلبي.'))
    if flow is not None:(supporting if flow>0 else weakening).append('قياس ضغط التداول '+value(flow)+'، '+('يميل للشراء.' if flow>0 else 'يميل للبيع.'))
    if vr is not None and vr<1:weakening.append('حجم التداول '+value(vr)+' من متوسطه، تأكيد الحركة بالحجم محدود.')
    if adx is not None and adx<20:weakening.append('قياس قوة الاتجاه '+value(adx)+' أقل من20، تأكيد الاتجاه ضعيف.')
    lines=['📌 '+LRI+item['ticker']+PDI,'📅 جلسة '+LRI+item['history_as_of']+PDI,metric('💵 آخر إغلاق',c,'جنيه'),
           '\nالخلاصة','• '+trend,'• '+momentum,
           '\n✅ ما يدعم القراءة']+['• '+x for x in supporting[:3]]
    if not supporting:lines.append('لا تأكيد إيجابي واضح من القياسات المتاحة.')
    lines+=['\n⚠️ ما يضعفها']+['• '+x for x in weakening[:3]]
    if not weakening:lines.append('عدم ظهور ضعف في القياسات لا يعني غياب المخاطر.')
    lines+=['\n📍 إيه اللي يغيّر القراءة؟',metric('المقاومة السابقة',resistance,'جنيه')]
    if resistance is not None:
        lines.append(('الإغلاق فوقها لاحقًا، مع تداول أقوى، سيكون تأكيدًا حسابيًا لتجاوز القمة السابقة.' if c<=resistance else 'الإغلاق الحالي أعلى منها؛ استمرار الثبات فوقها يحتاج متابعة جلسات لاحقة.'))
    lines +=[metric('الدعم السابق',support,'جنيه')]
    if support is not None:lines.append('إغلاق لاحق تحته يضعف القراءة بكسر القاع السابق. الدعم مش ضمان لوقف النزول.')
    lines+=['دي شروط متابعة، مش توقع ولا أمر شراء أو بيع.']
    t=item.get('levels')
    if t:
        lines+=['\n🎯 سيناريو حسابي، مش توقع',metric('مرجع الحساب، آخر إغلاق',t['reference']),metric('حد خسارة نظري',t['stop']),metric('مستوى صعود أول',t['tp1']),metric('مستوى صعود ثانٍ',t['tp2']),'دي مستويات محسوبة من التذبذب والدعم، مش أمر شراء أو بيع، ومش وعد بوصول السعر.']
    else:lines+=['\nالمستويات النظرية غير متاحة لعدم كفاية البيانات.']
    holding=item.get('_holding')
    if holding:
        lines+=['\n💼 علاقته بمحفظتك المحفوظة',metric('متوسط شرائك',holding['buy_price'],'جنيه'),metric('فرق السعر عن التكلفة',holding['pnl_pct'],'%'),'فرق حسابي فقط، قبل مطابقة التوزيعات والتجزئات. الوصول لمتوسط الشراء مش هدف فني في حد ذاته.']
    lines+=['\n⚠️ إيه اللي ناقص؟']
    if item.get('selected_open') is None:lines.append('سعر الفتح مش متسق، لذلك أي نمط شموع محتاجه غير متاح.')
    else:lines.append(metric('فتح نفس الجلسة',item['selected_open'],'جنيه')+'، مش دليل إن تاريخ الشموع كله سليم.')
    lines+=['التقييم الإجمالي واحتمال النجاح وموعد وصول السعر غير متاحين، مش هنحط أرقام تخمينية.','دي قراءة يومية سابقة، مش سعر لحظي ولا متابعة داخل الجلسة.']
    if item['gap_dates']:lines.append('فيه صف إغلاق ناقص بتاريخ '+LRI+', '.join(item['gap_dates'])+PDI+'، الحساب على المشاهدات المتاحة.')
    lines+=['\nتفاصيل المؤشرات الفنية موجودة في التطبيق.','ملاحظات المصدر والحساب مرة واحدة في آخر التقرير.']
    return '\n'.join(lines)+'\n\n'


def common_notes(records):
    gaps=sorted({d for r in records for d in r.get('gap_dates',[])})
    return '\n'.join(['ℹ️ ملحوظة التقرير','المصدر: Yahoo Finance، الأسعار بالجنيه المصري.','الأسعار مؤرخة وليست لحظية، ولا نعتبر شمعة اليوم نهائية قبل التحقق.',
        'تقويم السوق وأسعار البورصة وأثر التوزيعات غير متحقق منها مستقلًا. قد توجد تواريخ غائبة غير الصفوف الفارغة المرصودة.',
        'وصف Yahoo للأداة: '+', '.join(sorted({r.get('instrument_type','unknown') for r in records}))+'، وصف غير معتمد هنا.',
        'النوافذ بعدد المشاهدات المتاحة، دون تعويض أسعار. لا إثبات لأداء استراتيجية أو احتمال نجاح أو موعد هدف.',
        'المستويات النظرية: الوقف هو الأوسع بين الإغلاق ناقص2×ATR والدعم ناقص0.5×ATR إذا كان الدعم دون الإغلاق. R هو فرق المرجع والوقف؛ TP1=2R وTP2=3R. لا تشمل تكاليف التنفيذ والانزلاق.',
        'المحفظة الخاصة مبنية على الكميات ومتوسطات الشراء المحفوظة باختيار المستخدم، وليست مزامنة مع وسيط.',
        'فروق المحفظة حسابية فقط. يلزم مطابقة التجزئات وزيادات رأس المال والتوزيعات مع الكميات والتكلفة قبل اعتبارها عائدًا استثماريًا. لا تشمل عمولات أو ضرائب أو توزيعات أو تكلفة خروج.',
        'للبحث والوصف، لا توصية شخصية بشراء أو بيع أو احتفاظ، ولا عوائد مضمونة.'])


def portfolio_card(row):
    lines=['💼 '+LRI+row['ticker']+PDI,
           '📅 جلسة '+(LRI+row['date']+PDI if row['date'] else 'غير متاحة'),
           '📦 الكمية  '+LRI+f"{row['shares']:,}"+PDI,
           'متوسط الشراء  '+LRI+row['buy_price']+PDI+' ج.م',
           metric('التكلفة',row['cost'],'ج.م')]
    if row['close'] is None:
        lines+=['⚠️ سعر Yahoo غير متاح.','القيمة والفرق السعري  غير متاح.','المركز محفوظ، لا يُحذف ولا يُقيّم بصفر.']
    else:
        lines +=[metric('💵 إغلاق المصدر',row['close'],'ج.م'),metric('القيمة الحسابية',row['value'],'ج.م'),metric('الفرق السعري غير المحقق',row['pnl'],'ج.م'),metric('نسبة الفرق',row['pnl_pct'],'%')]
        t=row['technical']
        lines+=['\n📍 مناطق متابعة',metric('الدعم',t.get('Support_20')),metric('المقاومة',t.get('Resistance_20')),metric('حد متابعة التذبذب النظري',t.get('Chandelier_22')),'مستوى حسابي، لا أمر بيع.']
    lines+=['\nالأساس: آخر محفظة في الكود باختيارك.','الفرق السعري ليس عائدًا معتمدًا قبل مطابقة التوزيعات والتجزئات.','باقي حدود المصدر في ملحوظة التقرير.']
    return '\n'.join(lines)+'\n\n'


def compact_messages(records,snapshot=None):
    from report import _chunk
    by_ticker={r['ticker']:r for r in (snapshot or {}).get('rows',[])}
    records=[dict(r) for r in records]
    for record in records:
        holding=by_ticker.get(record['ticker'].replace('.CA',''))
        record['_holding']=holding
    messages=[technical_card(r) for r in records]
    if snapshot:
        messages+=_chunk([portfolio_card(r) for r in snapshot['rows']],'',limit=3800)
        lines=['📊 ملخص المحفظة',f"المراكز المحفوظة  {snapshot['count']}",f"المراكز المسعّرة  {snapshot['valued_count']}",metric('التكلفة المحفوظة لكل المراكز',snapshot['total_stored_cost'],'ج.م')]
        if snapshot['covered_value'] is not None:
            lines+=['\nالجزء المسعّر فقط، ليس إجمالي المحفظة',metric('تكلفته',snapshot['covered_cost'],'ج.م'),metric('قيمته',snapshot['covered_value'],'ج.م'),metric('فرق سعري حسابي',snapshot['covered_pnl'],'ج.م')]
        if not snapshot['complete']:lines+=['⚠️ إجمالي قيمة المحفظة والربح/الخسارة غير متاح لعدم اكتمال الأسعار. لا نحتسب الناقص بصفر.']
        lines+=['الأساس المحفوظ لا يحدد رأس المال المتاح لصفقة جديدة أو نسبة المخاطرة.']
        messages.append('\n'.join(lines))
    if records:messages.append(common_notes(records))
    return messages
