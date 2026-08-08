import os

# ==========================
# Telegram Configuration
# ==========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set")

if not ADMIN_CHAT_ID:
    raise ValueError("ADMIN_CHAT_ID is not set")


# ==========================
# Trading Configuration
# ==========================

TOTAL_CAPITAL = 100000

# أقصى مخاطرة في الصفقة = 1% من رأس المال
RISK_PER_TRADE = 0.01

# أقل Score يسمح بإظهار السهم
MIN_SCORE_THRESHOLD = 75


# ==========================
# EGX Sharia Stocks
# ==========================

SHARIA_EGX_STOCKS = [
    "TMGH.CA",
    "SWDY.CA",
    "MFPC.CA",
    "ABUK.CA",
    "ADIB.CA",
    "OCDI.CA",
    "PHDC.CA",
    "AMOC.CA",
    "ETEL.CA",
    "SKPC.CA",
    "HELI.CA",
]
