"""
Configuration management for Autonomous Lead Enrichment Agent.
Loads settings from environment variables and .env file.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini API Configuration
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # External Search Configuration (Optional)
    tavily_api_key: Optional[str] = None

    # Crawler Settings
    max_subpages: int = 5
    page_timeout_ms: int = 15000
    max_tokens_budget: int = 7000
    headless: bool = True

    # Output paths
    output_dir: Path = Path("output")
    scratch_dir: Path = Path("output/scratch")


settings = Settings()
