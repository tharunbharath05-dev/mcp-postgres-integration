import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration loaded from environment variables."""
    database_url: str
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "Settings":
        db_url = os.getenv("DATABASE_URL", "").strip()
        if not db_url:
            raise EnvironmentError(
                "CRITICAL: DATABASE_URL is missing. Set it in your .env file or environment."
            )
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        return cls(database_url=db_url, log_level=log_level)


settings = Settings.load()