from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """
    Application configuration loaded from Environment Variables or .env file.
    Default values replace the hardcoded constants.
    """

    CONFIG_FILE: Path = Path("desired_state.yaml")
    POLLING_INTERVAL: int = 5
    CONTROL_INTERVAL: float = 0.1
    DOCKER_BASE_URL: str | None = None  # Optional: Connect to remote docker

    ROGUE_IMAGE: str = "httpd:alpine"
    ROGUE_PORT: int = 8080

    model_config = SettingsConfigDict(env_prefix="DRIFT_")


@lru_cache
def get_settings() -> AppSettings:
    """
    Creates a singleton instance of AppSettings.
    Uses lru_cache to ensure the .env file is read only once.
    """
    return AppSettings()


settings = get_settings()
