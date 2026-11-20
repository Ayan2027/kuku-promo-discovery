
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

def resolve_data_path(env_name: str, default: str) -> Path:
    value = Path(os.getenv(env_name, default))
    if not value.is_absolute():
        value = BASE_DIR / value
    return value.resolve()


class Settings:
    APP_ENV = os.getenv("APP_ENV", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    DATA_DIR = resolve_data_path("DATA_DIR", "data")
    INPUT_DIR = resolve_data_path("INPUT_DIR", "data/input")
    PROCESSED_DIR = resolve_data_path(
        "PROCESSED_DIR", "data/processed"
    )
    CACHE_DIR = resolve_data_path("CACHE_DIR", "data/cache")
    EXPORT_DIR = resolve_data_path("EXPORT_DIR", "data/exports")

    PROMO_MIN_DURATION = int(
        os.getenv("PROMO_MIN_DURATION", "20")
    )
    PROMO_MAX_DURATION = int(
        os.getenv("PROMO_MAX_DURATION", "60")
    )

    @classmethod
    def validate(cls):
        if cls.PROMO_MIN_DURATION <= 0:
            raise ValueError("Minimum promo duration must be positive.")

        if cls.PROMO_MAX_DURATION < cls.PROMO_MIN_DURATION:
            raise ValueError("Maximum duration cannot be less than minimum.")

    @classmethod
    def create_directories(cls):
        for directory in [
            cls.DATA_DIR,
            cls.INPUT_DIR,
            cls.PROCESSED_DIR,
            cls.CACHE_DIR,
            cls.EXPORT_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.validate()
settings.create_directories()
