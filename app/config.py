from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Discord
    DISCORD_BOT_TOKEN: str = ""

    # eSewa Configuration (ePay v2 Test Credentials)
    ESEWA_PRODUCT_CODE: str = "EPAYTEST"
    ESEWA_SECRET_KEY: str = "8gBm/:&EnhH.1/q"
    ESEWA_PAYMENT_URL: str = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
    ESEWA_VERIFY_URL: str = "https://rc-epay.esewa.com.np/api/epay/transaction/status/"

    # Store Settings
    STORE_NAME: str = "Pasale Dai Collections"
    STORE_PHONE: str = "+977-9800000000"
    STORE_EMAIL: str = "support@pasaledai.com"
    STORE_ADDRESS: str = "Kathmandu, Nepal"
    BASE_URL: str = "https://k67gl3qt-8000.inc1.devtunnels.ms/"

    # Persistence & Memory
    DATABASE_URL: str = "sqlite:///./data/store.db"
    MEMORY_MESSAGE_LIMIT: int = 15

    # Directory Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    INVOICES_DIR: Path = BASE_DIR / "invoices"
    PRODUCTS_DIR: Path = BASE_DIR / "products"
    MEMORY_DIR: Path = BASE_DIR / "memory"

    def setup_directories(self) -> None:
        """Ensure runtime directories exist."""
        for path in [self.DATA_DIR, self.INVOICES_DIR, self.PRODUCTS_DIR, self.MEMORY_DIR]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.setup_directories()