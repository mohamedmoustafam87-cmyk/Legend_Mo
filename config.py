import os


# ==========================================================
# Telegram Configuration
# ==========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set")

if not ADMIN_CHAT_ID:
    raise ValueError("ADMIN_CHAT_ID is not set")


# ==========================================================
# Trading Configuration
# ==========================================================

TOTAL_CAPITAL = 100000

# أقصى مخاطرة في الصفقة الواحدة = 1%
RISK_PER_TRADE = 0.01

# أقل Score لإظهار السهم
MIN_SCORE_THRESHOLD = 60


# ==========================================================
# EGX Official Holidays 2026
#
# مصدر التواريخ: بيانات رسمية من البورصة المصرية ومجلس
# الوزراء (تم التحقق منها بالبحث في أغسطس 2026).
#
# ⚠️ مهم جداً: القائمة دي لازم تتحدّث كل سنة يدوياً، لأن
# مواعيد الأعياد الهجرية (عيد الفطر/الأضحى/المولد النبوي)
# بتتغير كل سنة ومفيش صيغة حسابية بسيطة موثوقة تحسبها،
# وبعض الإجازات بتترحّل بقرار من مجلس الوزراء.
#
# راجع دايماً: https://www.egx.com.eg/ar/Trading_Calendar.aspx
# ==========================================================

EGX_HOLIDAYS_2026 = {

    # عيد الفطر المبارك (إجازة رسمية معلنة من البورصة)
    "2026-03-19",
    "2026-03-20",
    "2026-03-21",
    "2026-03-22",
    "2026-03-23",

    # عيد الأضحى المبارك (إجازة رسمية معلنة من البورصة)
    "2026-05-26",
    "2026-05-27",
    "2026-05-28",
    "2026-05-29",
    "2026-05-30",
    "2026-05-31",

    # المولد النبوي الشريف
    "2026-08-26",

    # عيد القوات المسلحة / نصر أكتوبر
    "2026-10-06",

    # ملاحظة: تم استبعاد الأعياد اللي فاتت فعلياً (زي 7 يناير،
    # 25 يناير، 25 أبريل، 1 مايو، 30 يونيو، 23 يوليو) من التقويم
    # ده لأنها غير مؤثرة على تشغيل البوت حالياً (بعد تاريخها)،
    # لكن لو شغّلت البوت على بيانات تاريخية قبل ده، ضيفها هنا.
}


# ==========================================================
# EGX STOCK UNIVERSE
# ==========================================================
#
# جميع الأسهم الموجودة في قائمة EGX الحالية.
# ==========================================================

EGX_STOCKS = [

    "COMI.CA",
    "SWDY.CA",
    "TMGH.CA",
    "ETEL.CA",
    "EGAL.CA",
    "QNBE.CA",
    "EAST.CA",
    "MFPC.CA",
    "ABUK.CA",
    "ALCN.CA",
    "HDBK.CA",
    "EFIH.CA",
    "ADIB.CA",
    "ORAS.CA",
    "FWRY.CA",
    "EMFD.CA",
    "SCTS.CA",
    "ORHD.CA",
    "EFID.CA",
    "PHDC.CA",
    "GPPL.CA",
    "OCDI.CA",
    "HRHO.CA",
    "VLMR.CA",
    "VLMRA.CA",
    "JUFO.CA",
    "CANA.CA",
    "BTFH.CA",
    "GBCO.CA",
    "BIOC.CA",
    "HELI.CA",
    "IRON.CA",
    "RAYA.CA",
    "FERC.CA",
    "CIEB.CA",
    "FAIT.CA",
    "FAITA.CA",
    "EXPA.CA",
    "EGCH.CA",
    "CLHO.CA",
    "VALU.CA",
    "ARCC.CA",
    "CCAP.CA",
    "PHAR.CA",
    "CIRA.CA",
    "MTIE.CA",
    "EFIC.CA",
    "SCEM.CA",
    "TAQA.CA",
    "EGTS.CA",
    "SKPC.CA",
    "POUL.CA",
    "MCQE.CA",
    "ORWE.CA",
    "MASR.CA",
    "SAUD.CA",
    "EGSA.CA",
    "MOIL.CA",
    "UBEE.CA",
    "NIPH.CA",
    "AMES.CA",
    "EGBE.CA",
    "ISPH.CA",
    "MBSC.CA",
    "TALM.CA",
    "MHOT.CA",
    "CICH.CA",
    "RMDA.CA",
    "ATQA.CA",
    "AMOC.CA",
    "CSAG.CA",
    "BINV.CA",
    "IFAP.CA",
    "MPRC.CA",
    "OLFI.CA",
    "MOIN.CA",
    "PRDC.CA",
    "MIPH.CA",
    "ISMQ.CA",
    "OIH.CA",
    "BONY.CA",
    "EGAS.CA",
    "DOMT.CA",
    "PHTV.CA",
    "SPHT.CA",
    "KORA.CA",
    "AFMC.CA",
    "ZMID.CA",
    "CPCI.CA",
    "MPCI.CA",
    "ELEC.CA",
    "ACAP.CA",
    "NINH.CA",
    "SUGR.CA",
    "NAPR.CA",
    "ENGC.CA",
    "AMIA.CA",
    "AXPH.CA",
    "GOUR.CA",
    "CNFN.CA",
    "ARAB.CA",
    "OCPH.CA",
    "SPIN.CA",
    "DSCW.CA",
    "MICH.CA",
    "AMER.CA",
    "GSSC.CA",
    "MFSC.CA",
    "KABO.CA",
    "SVCE.CA",
    "WCDF.CA",
    "GDWA.CA",
    "UNIT.CA",
    "OFH.CA",
    "UEFM.CA",
    "AJWA.CA",
    "SDTI.CA",
    "SAIB.CA",
    "ADCI.CA",
    "ASCM.CA",
    "ELKA.CA",
    "ELSH.CA",
    "ACTF.CA",
    "ACGC.CA",
    "ACAMD.CA",
    "ISMA.CA",
    "INFI.CA",
    "LCSW.CA",
    "SMFR.CA",
    "CRST.CA",
    "KZPC.CA",
    "ZEOT.CA",
    "ALRA.CA",
    "DAPH.CA",
    "CFGH.CA",
    "EDFM.CA",
    "ETRS.CA",
    "GGCC.CA",
    "NARE.CA",
    "PHGC.CA",
    "MILS.CA",
    "ATLC.CA",
    "ADPC.CA",
    "GGRN.CA",
    "RACC.CA",
    "CEFM.CA",
    "MPCO.CA",
    "EALR.CA",
    "GPIM.CA",
    "IDRE.CA",
    "NAHO.CA",
    "UEGC.CA",
    "AALR.CA",
    "EHDR.CA",
    "MAAL.CA",
    "SNFC.CA",
    "ECAP.CA",
    "WKOL.CA",
    "MOSC.CA",
    "PRCL.CA",
    "ODIN.CA",
    "SCFM.CA",
    "MENA.CA",
    "NCCW.CA",
    "CERA.CA",
    "CAED.CA",
    "GTWL.CA",
    "DEIN.CA",
    "DTPP.CA",
    "NHPS.CA",
    "SEIG.CA",
    "SEIGA.CA",
    "OBRI.CA",
    "MEPA.CA",
    "SIPC.CA",
    "NDRL.CA",
    "AIDC.CA",
    "RREI.CA",
    "AFDI.CA",
    "AMII.CA",
    "COSG.CA",
    "EBSC.CA",
    "ALUM.CA",
    "POCO.CA",
    "LUTS.CA",
    "PRMH.CA",
    "RTVC.CA",
    "TANM.CA",
    "UNIP.CA",
    "ASPI.CA",
    "GTEX.CA",
    "MCRO.CA",
    "APSW.CA",
    "ICID.CA",
    "KRDI.CA",
    "TYCN.CA",
    "ROTO.CA",
    "SPMD.CA",
    "AIHC.CA",
    "MEGM.CA",
    "ICLE.CA",
    "RUBX.CA",
    "EASB.CA",
    "KWIN.CA",
    "RAKT.CA",
    "MOED.CA",
    "AREH.CA",
    "EEII.CA",
    "CCRS.CA",
    "EPCO.CA",
    "GRCA.CA",
    "GIHD.CA",
    "ELWA.CA",
    "ELNA.CA",
    "DGTZ.CA",
    "DCCC.CA",
    "MMAT.CA",
    "NEDA.CA",
    "TRTO.CA",
    "EPPK.CA",
    "GMCI.CA",
    "EOSB.CA",
    "CPME.CA",
    "COPR.CA",
]


# ==========================================================
# SHARIA FILTER (Disabled / All Stocks Included)
# ==========================================================

SHARIA_EGX_STOCKS = EGX_STOCKS


# ==========================================================
# Liquidity Configuration
# ==========================================================

MIN_AVG_DAILY_VALUE = 1_000_000

MIN_AVG_VOLUME = 10_000


# ==========================================================
# Technical Indicators Configuration
# ==========================================================

RSI_PERIOD = 14

ATR_PERIOD = 14

EMA_FAST = 20

EMA_SLOW = 50

MA_LONG = 200

ADX_PERIOD = 14

MACD_FAST = 12

MACD_SLOW = 26

MACD_SIGNAL = 9

VOLUME_MA_PERIOD = 20

SUPPORT_RESISTANCE_PERIOD = 20


# ==========================================================
# Investment Horizon
# ==========================================================

ONE_MONTH_SESSIONS = 21

TWO_MONTH_SESSIONS = 42


# ==========================================================
# Entry Configuration
# ==========================================================

MAX_DISTANCE_FROM_EMA20 = 5.0


# ==========================================================
# Risk Management
# ==========================================================

ATR_STOP_MULTIPLIER = 2.0

SUPPORT_ATR_BUFFER = 0.5

TP1_R_MULTIPLE = 2.0

TP2_R_MULTIPLE = 3.0
