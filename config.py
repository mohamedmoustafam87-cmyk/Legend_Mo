import os
import re
from zoneinfo import ZoneInfo

_BASE = os.path.dirname(os.path.abspath(__file__))

# ==========================================================
# Telegram (لا يتم رفع خطأ وقت الاستيراد - يتحقق منه البوت فقط)
# ==========================================================

# تحذير: القيم هنا مكتوبة داخل الكود بطلب صاحب المشروع.
# لو الريبو Public أي حد يقدر يشوف التوكن ويتحكم في البوت.
# الأفضل: ريبو Private، أو رجّع القراءة من GitHub Secrets (os.getenv).
TELEGRAM_TOKEN = "8636770275:AAEvrJ289sEUW1Yr2f2qBcB1Tsd2z1dcsc"
ADMIN_CHAT_ID = "88742271"


def require_telegram():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN is not set")
    if not ADMIN_CHAT_ID:
        raise ValueError("ADMIN_CHAT_ID is not set")

    # فحص شكل التوكن (بدون طباعته): الجزء بعد ":" عادةً 35 حرف
    if not re.fullmatch(r"\d{8,10}:[A-Za-z0-9_-]{35}", str(TELEGRAM_TOKEN)):
        secret_len = len(str(TELEGRAM_TOKEN).split(":")[-1])
        print(
            f"⚠️ شكل TELEGRAM_TOKEN غير معتاد (طول الجزء بعد ':' = {secret_len}، المعتاد 35). "
            "لو تيليجرام رد بـ Unauthorized أعد نسخ التوكن كاملاً من BotFather."
        )

    if not str(ADMIN_CHAT_ID).lstrip("-").isdigit():
        print("⚠️ ADMIN_CHAT_ID لازم يكون رقم (للجروب بيبدأ بـ -).")


# ==========================================================
# Trading / Risk
# ==========================================================

TOTAL_CAPITAL = 100000
RISK_PER_TRADE = 0.01            # أقصى خسارة للصفقة = 1% من رأس المال
MAX_POSITION_PCT = 0.20          # أقصى حجم للصفقة الواحدة = 20% من رأس المال
MIN_SCORE_THRESHOLD = 60         # يُستخدم فقط عند غياب نتائج الـ backtest
MAX_REPORT_STOCKS = 5

# مضاعف حجم الصفقة حسب حالة السوق (اتساع السوق Breadth)
REGIME_SIZE_MULT = {"low": 0.5, "mid": 0.75, "high": 1.0}


# ==========================================================
# EGX STOCK UNIVERSE
# ==========================================================

EGX_STOCKS = [
    "COMI.CA", "SWDY.CA", "TMGH.CA", "ETEL.CA", "EGAL.CA", "QNBE.CA", "EAST.CA", "MFPC.CA", "ABUK.CA", "ALCN.CA",
    "HDBK.CA", "EFIH.CA", "ADIB.CA", "ORAS.CA", "FWRY.CA", "EMFD.CA", "SCTS.CA", "ORHD.CA", "EFID.CA", "PHDC.CA",
    "GPPL.CA", "OCDI.CA", "HRHO.CA", "VLMR.CA", "VLMRA.CA", "JUFO.CA", "CANA.CA", "BTFH.CA", "GBCO.CA", "BIOC.CA",
    "HELI.CA", "IRON.CA", "RAYA.CA", "FERC.CA", "CIEB.CA", "FAIT.CA", "FAITA.CA", "EXPA.CA", "EGCH.CA", "CLHO.CA",
    "VALU.CA", "ARCC.CA", "CCAP.CA", "PHAR.CA", "CIRA.CA", "MTIE.CA", "EFIC.CA", "SCEM.CA", "TAQA.CA", "EGTS.CA",
    "SKPC.CA", "POUL.CA", "MCQE.CA", "ORWE.CA", "MASR.CA", "SAUD.CA", "EGSA.CA", "MOIL.CA", "UBEE.CA", "NIPH.CA",
    "AMES.CA", "EGBE.CA", "ISPH.CA", "MBSC.CA", "TALM.CA", "MHOT.CA", "CICH.CA", "RMDA.CA", "ATQA.CA", "AMOC.CA",
    "CSAG.CA", "BINV.CA", "IFAP.CA", "MPRC.CA", "OLFI.CA", "MOIN.CA", "PRDC.CA", "MIPH.CA", "ISMQ.CA", "OIH.CA",
    "BONY.CA", "EGAS.CA", "DOMT.CA", "PHTV.CA", "SPHT.CA", "KORA.CA", "AFMC.CA", "ZMID.CA", "CPCI.CA", "MPCI.CA",
    "ELEC.CA", "ACAP.CA", "NINH.CA", "SUGR.CA", "NAPR.CA", "ENGC.CA", "AMIA.CA", "AXPH.CA", "GOUR.CA", "CNFN.CA",
    "ARAB.CA", "OCPH.CA", "SPIN.CA", "DSCW.CA", "MICH.CA", "AMER.CA", "GSSC.CA", "MFSC.CA", "KABO.CA", "SVCE.CA",
    "WCDF.CA", "GDWA.CA", "UNIT.CA", "OFH.CA", "UEFM.CA", "AJWA.CA", "SDTI.CA", "SAIB.CA", "ADCI.CA", "ASCM.CA",
    "ELKA.CA", "ELSH.CA", "ACTF.CA", "ACGC.CA", "ACAMD.CA", "ISMA.CA", "INFI.CA", "LCSW.CA", "SMFR.CA", "CRST.CA",
    "KZPC.CA", "ZEOT.CA", "ALRA.CA", "DAPH.CA", "CFGH.CA", "EDFM.CA", "ETRS.CA", "GGCC.CA", "NARE.CA", "PHGC.CA",
    "MILS.CA", "ATLC.CA", "ADPC.CA", "GGRN.CA", "RACC.CA", "CEFM.CA", "MPCO.CA", "EALR.CA", "GPIM.CA", "IDRE.CA",
    "NAHO.CA", "UEGC.CA", "AALR.CA", "EHDR.CA", "MAAL.CA", "SNFC.CA", "ECAP.CA", "WKOL.CA", "MOSC.CA", "PRCL.CA",
    "ODIN.CA", "SCFM.CA", "MENA.CA", "NCCW.CA", "CERA.CA", "CAED.CA", "GTWL.CA", "DEIN.CA", "DTPP.CA", "NHPS.CA",
    "SEIG.CA", "SEIGA.CA", "OBRI.CA", "MEPA.CA", "SIPC.CA", "NDRL.CA", "AIDC.CA", "RREI.CA", "AFDI.CA", "AMII.CA",
    "COSG.CA", "EBSC.CA", "ALUM.CA", "POCO.CA", "LUTS.CA", "PRMH.CA", "RTVC.CA", "TANM.CA", "UNIP.CA", "ASPI.CA",
    "GTEX.CA", "MCRO.CA", "APSW.CA", "ICID.CA", "KRDI.CA", "TYCN.CA", "ROTO.CA", "SPMD.CA", "AIHC.CA", "MEGM.CA",
    "ICLE.CA", "RUBX.CA", "EASB.CA", "KWIN.CA", "RAKT.CA", "MOED.CA", "AREH.CA", "EEII.CA", "CCRS.CA", "EPCO.CA",
    "GRCA.CA", "GIHD.CA", "ELWA.CA", "ELNA.CA", "DGTZ.CA", "DCCC.CA", "MMAT.CA", "NEDA.CA", "TRTO.CA", "EPPK.CA",
    "GMCI.CA", "EOSB.CA", "CPME.CA", "COPR.CA",
]


def _load_symbols_file(name):
    path = os.path.join(_BASE, name)
    if not os.path.exists(path):
        return None
    out = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.split("#")[0].strip().upper()
            if s:
                out.add(s if s.endswith(".CA") else s + ".CA")
    return out or None


# ==========================================================
# SHARIA FILTER
# ضع قائمتك المعتمدة في ملف sharia_stocks.txt (رمز في كل سطر).
# بدون الملف الفلتر غير مفعّل (القائمة الحالية فيها بنوك تقليدية).
# ==========================================================

_sharia = _load_symbols_file("sharia_stocks.txt")
SHARIA_FILTER_ACTIVE = _sharia is not None
SHARIA_EGX_STOCKS = (
    [s for s in EGX_STOCKS if s in _sharia] if _sharia else list(EGX_STOCKS)
)


# ==========================================================
# Liquidity
# ==========================================================

MIN_AVG_DAILY_VALUE = 1_000_000
MIN_AVG_VOLUME = 10_000
MIN_ACTIVE_DAYS = 18             # أيام فيها تداول من آخر 20 جلسة


# ==========================================================
# Technical Indicators
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
MIN_HISTORY_ROWS = 220


# ==========================================================
# Horizon / Entry / Risk (كما هي)
# ==========================================================

ONE_MONTH_SESSIONS = 21
TWO_MONTH_SESSIONS = 42

MAX_DISTANCE_FROM_EMA20 = 5.0
MAX_ALLOWABLE_RSI = 72.0
MAX_ENTRY_DISTANCE_PERCENT = 2.5

ATR_STOP_MULTIPLIER = 2.0
SUPPORT_ATR_BUFFER = 0.5
TP1_R_MULTIPLE = 2.0
TP2_R_MULTIPLE = 3.0


# ==========================================================
# Schedule / Trading calendar
# ==========================================================

TIMEZONE_NAME = "Africa/Cairo"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)

REPORT_TIMES = [(10, 30), (12, 30), (14, 30), (15, 0)]
REPORT_TIME_TOLERANCE_MINUTES = 5

# أيام التداول: الأحد..الخميس (Python: Monday=0 ... Sunday=6)
TRADING_WEEKDAYS = {6, 0, 1, 2, 3}

# الجلسة تُعتبر مكتملة بعد (إغلاق + هامش)
MARKET_CLOSE = (14, 30)
BAR_COMPLETE_BUFFER_MIN = 20

# إجازات البورصة: ضعها في egx_holidays.txt (YYYY-MM-DD في كل سطر)
EGX_HOLIDAYS = set()
_hol = os.path.join(_BASE, "egx_holidays.txt")
if os.path.exists(_hol):
    with open(_hol, encoding="utf-8") as _f:
        for _line in _f:
            _d = _line.split("#")[0].strip()
            if _d:
                EGX_HOLIDAYS.add(_d)


# ==========================================================
# Backtest / Model
# ==========================================================

ROUND_TRIP_COST_PCT = 0.5        # عمولات + ضرائب + انزلاق (عدّلها حسب شركتك)
MODEL_STATS_FILE = os.getenv(
    "MODEL_STATS_FILE", os.path.join(_BASE, "model_stats.json")
)
CONTEXT_FILE = os.getenv(
    "CONTEXT_FILE", os.path.join(_BASE, "market_context.json")
)
MAX_WORKERS = 6
