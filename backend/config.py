"""
ShopSpy Configuration Module

Centralized configuration management using environment variables.
All settings are loaded at startup and validated.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Environment(Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class DatabaseConfig:
    """Database configuration."""

    path: str = "data/shopspy.db"

    @property
    def full_path(self) -> str:
        """Get absolute path to database."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, self.path)


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""

    bot_token: Optional[str] = None
    enabled: bool = False

    def __post_init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.enabled = bool(self.bot_token)


@dataclass
class AIConfig:
    """AI providers configuration."""

    # Gemini (free tier)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_max_tokens: int = 4000
    gemini_temperature: float = 0.3

    # Claude (paid)
    claude_api_key: Optional[str] = None
    claude_model: str = "claude-3-haiku-20240307"
    claude_max_tokens: int = 2000

    # Rate limiting
    rate_limit_per_ip: int = 10
    rate_limit_global: int = 200

    def __post_init__(self):
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.claude_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.gemini_model = os.environ.get("GEMINI_MODEL", self.gemini_model)
        self.gemini_max_tokens = int(
            os.environ.get("GEMINI_MAX_TOKENS", self.gemini_max_tokens)
        )
        self.gemini_temperature = float(
            os.environ.get("GEMINI_TEMPERATURE", self.gemini_temperature)
        )
        self.rate_limit_per_ip = int(
            os.environ.get("RATE_LIMIT_PER_IP", self.rate_limit_per_ip)
        )
        self.rate_limit_global = int(
            os.environ.get("RATE_LIMIT_GLOBAL", self.rate_limit_global)
        )

    @property
    def available_provider(self) -> Optional[str]:
        """Get available AI provider (Gemini has priority as it's free)."""
        if self.gemini_api_key:
            return "gemini"
        if self.claude_api_key:
            return "claude"
        return None


@dataclass
class ServerConfig:
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list = field(default_factory=lambda: ["*"])

    def __post_init__(self):
        self.host = os.environ.get("HOST", self.host)
        self.port = int(os.environ.get("PORT", self.port))
        self.debug = os.environ.get("DEBUG", "false").lower() == "true"


@dataclass
class Config:
    """Main application configuration."""

    env: Environment = Environment.DEVELOPMENT
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    def __post_init__(self):
        env_str = os.environ.get("ENVIRONMENT", "development").lower()
        self.env = (
            Environment(env_str)
            if env_str in [e.value for e in Environment]
            else Environment.DEVELOPMENT
        )

        # Override for production
        if self.env == Environment.PRODUCTION:
            self.server.debug = False

    @property
    def is_production(self) -> bool:
        return self.env == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.env == Environment.DEVELOPMENT


# Global configuration instance
config = Config()
