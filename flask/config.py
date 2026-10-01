import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Check both current directory and parent directory for .env
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "pdc-super-secret-production-key-9f8a3c2e1b")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpass123")
    
    # Store Base URL (used for generating payment / checkout URLs)
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    
    # Database path: check environment or use data/store.db
    # Guaranteed absolute path to avoid directory mismatch between bot and web server
    DATA_DIR = (BASE_DIR.parent / "data").resolve()
    DB_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "store.db"))).resolve()
    INVOICES_DIR = (BASE_DIR.parent / "invoices").resolve()
    
    # eSewa Configuration (UAT / Test credentials by default)
    ESEWA_MERCHANT_CODE = os.getenv("ESEWA_MERCHANT_CODE", "EPAYTEST")
    ESEWA_SECRET_KEY = os.getenv("ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")
    ESEWA_PAYMENT_URL = os.getenv(
        "ESEWA_PAYMENT_URL", 
        "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
    )

    # Session Configuration
    SESSION_COOKIE_NAME = "pdc_admin_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

    @classmethod
    def ensure_directories(cls):
        """Ensure necessary storage directories exist at boot."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.INVOICES_DIR.mkdir(parents=True, exist_ok=True)

Config.ensure_directories()