from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env file."""

    football_data_api_key: str = ""
    competition_code: str = "WC"
    refresh_hour: int = 4
    admin_token: str = "change-me"
    database_url: str = "sqlite:///./wc.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Betting layer (mirrors the on-chain wc_betting program) ---
    usdc_decimals: int = 6
    standard_fee_bps: int = 500  # 5% house fee on profit for Standard-tier bettors
    premium_fee_bps: int = 200  # 2% reduced fee for Premium-tier bettors
    betting_program_id: str = ""  # Solana program id, once deployed to devnet

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
