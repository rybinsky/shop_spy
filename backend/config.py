"""
ShopSpy Configuration Module

Centralized configuration management using OmegaConf.
All settings loaded from config.yaml, secrets from environment variables.
"""

import os
from pathlib import Path
from typing import Optional

from omegaconf import DictConfig, OmegaConf

# ═══════════════════════════════════════════════════════════════
# Load configuration
# ═══════════════════════════════════════════════════════════════

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def _load_config() -> DictConfig:
    """Load configuration from YAML file with environment interpolation."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {_CONFIG_PATH}")

    # Load YAML
    cfg = OmegaConf.load(_CONFIG_PATH)

    # Register resolver for env vars (если не зарегистрирован)
    if not OmegaConf.has_resolver("oc.env"):
        OmegaConf.register_new_resolver(
            "oc.env", lambda var, default=None: os.environ.get(var, default)
        )

    # Resolve interpolations
    OmegaConf.resolve(cfg)

    return cfg


# Global config instance
cfg: DictConfig = _load_config()


# ═══════════════════════════════════════════════════════════════
# Helper properties for backward compatibility
# ═══════════════════════════════════════════════════════════════


class Config:
    """
    Configuration wrapper with property accessors.
    Provides backward compatibility with existing code.
    """

    # ── Environment ─────────────────────────────────────────────

    @property
    def env(self) -> str:
        return cfg.environment

    @property
    def is_production(self) -> bool:
        return cfg.environment == "production"

    @property
    def is_development(self) -> bool:
        return cfg.environment == "development"

    # ── Server ──────────────────────────────────────────────────

    @property
    def server(self) -> "ServerConfig":
        return ServerConfig()

    # ── Database ────────────────────────────────────────────────

    @property
    def database(self) -> "DatabaseConfig":
        return DatabaseConfig()

    # ── Telegram ────────────────────────────────────────────────

    @property
    def telegram(self) -> "TelegramConfig":
        return TelegramConfig()

    # ── Admin ───────────────────────────────────────────────────

    @property
    def admin(self) -> "AdminConfig":
        return AdminConfig()

    # ── AI ──────────────────────────────────────────────────────

    @property
    def ai(self) -> "AIConfig":
        return AIConfig()

    # ── Rate Limit ──────────────────────────────────────────────

    @property
    def rate_limit(self) -> "RateLimitConfig":
        return RateLimitConfig()

    # ── Price Analysis ──────────────────────────────────────────

    @property
    def price_analysis(self) -> "PriceAnalysisConfig":
        return PriceAnalysisConfig()

    # ── Prices ──────────────────────────────────────────────────

    @property
    def prices(self) -> "PricesConfig":
        return PricesConfig()

    # ── User Stats ──────────────────────────────────────────────

    @property
    def user_stats(self) -> "UserStatsConfig":
        return UserStatsConfig()

    # ── Cleanup ─────────────────────────────────────────────────

    @property
    def cleanup(self) -> "CleanupConfig":
        return CleanupConfig()

    # ── API ─────────────────────────────────────────────────────

    @property
    def api(self) -> "APIConfig":
        return APIConfig()


class ServerConfig:
    """Server configuration accessor."""

    @property
    def host(self) -> str:
        return cfg.server.host

    @property
    def port(self) -> int:
        return cfg.server.port

    @property
    def cors_origins(self) -> list:
        return list(cfg.server.cors_origins)


class DatabaseConfig:
    """Database configuration accessor."""

    @property
    def path(self) -> str:
        return cfg.database.path

    @property
    def full_path(self) -> str:
        """Get absolute path to database."""
        base_dir = Path(__file__).parent.parent
        return str(base_dir / cfg.database.path)


class TelegramConfig:
    """Telegram configuration accessor."""

    @property
    def bot_token(self) -> Optional[str]:
        token = cfg.telegram.bot_token
        return token if token else None

    @property
    def enabled(self) -> bool:
        return bool(cfg.telegram.bot_token)


class AdminConfig:
    """Admin configuration accessor."""

    @property
    def secret(self) -> Optional[str]:
        secret = cfg.admin.secret
        return secret if secret else None

    @property
    def is_protected(self) -> bool:
        return bool(cfg.admin.secret)


class AIConfig:
    """AI configuration accessor."""

    @property
    def gemini_api_key(self) -> Optional[str]:
        key = cfg.ai.gemini.api_key
        return key if key else None

    @property
    def gemini_model(self) -> str:
        return cfg.ai.gemini.model

    @property
    def gemini_max_tokens(self) -> int:
        return cfg.ai.gemini.max_tokens

    @property
    def gemini_temperature(self) -> float:
        return cfg.ai.gemini.temperature

    @property
    def claude_api_key(self) -> Optional[str]:
        key = cfg.ai.claude.api_key
        return key if key else None

    @property
    def claude_model(self) -> str:
        return cfg.ai.claude.model

    @property
    def claude_max_tokens(self) -> int:
        return cfg.ai.claude.max_tokens

    @property
    def available_provider(self) -> Optional[str]:
        """Get available AI provider (Gemini has priority)."""
        if self.gemini_api_key:
            return "gemini"
        if self.claude_api_key:
            return "claude"
        return None


class RateLimitConfig:
    """Rate limiting configuration accessor."""

    @property
    def per_ip(self) -> int:
        return cfg.rate_limit.per_ip

    @property
    def global_limit(self) -> int:
        # config.yaml stores this key as `global`
        return cfg.rate_limit["global"]


class PriceAnalysisConfig:
    """Price analysis configuration accessor."""

    @property
    def good_deal_threshold(self) -> float:
        return cfg.price_analysis.good_deal_threshold

    @property
    def overpriced_threshold(self) -> float:
        return cfg.price_analysis.overpriced_threshold

    @property
    def fake_discount_threshold(self) -> float:
        return cfg.price_analysis.fake_discount_threshold

    @property
    def min_price_margin(self) -> float:
        return cfg.price_analysis.min_price_margin

    @property
    def max_price_margin(self) -> float:
        return cfg.price_analysis.max_price_margin

    @property
    def notify_drop_percent(self) -> int:
        return cfg.price_analysis.notify_drop_percent

    @property
    def notify_rise_percent(self) -> int:
        return cfg.price_analysis.notify_rise_percent


class PricesConfig:
    """Prices repository configuration accessor."""

    @property
    def equality_threshold(self) -> float:
        return cfg.prices.equality_threshold

    @property
    def min_record_interval_hours(self) -> int:
        return cfg.prices.min_record_interval_hours


class UserStatsConfig:
    """User stats configuration accessor."""

    @property
    def view_dedup_days(self) -> int:
        return cfg.user_stats.view_dedup_days


class CleanupConfig:
    """Cleanup configuration accessor."""

    @property
    def interval_hours(self) -> int:
        return cfg.cleanup.interval_hours

    @property
    def keep_days(self) -> int:
        return cfg.cleanup.keep_days


class APIConfig:
    """API configuration accessor."""

    @property
    def history_limit_default(self) -> int:
        return cfg.api.history_limit_default

    @property
    def history_limit_max(self) -> int:
        return cfg.api.history_limit_max

    @property
    def products_limit_default(self) -> int:
        return cfg.api.products_limit_default

    @property
    def products_limit_max(self) -> int:
        return cfg.api.products_limit_max

    @property
    def recent_items_limit(self) -> int:
        return cfg.api.recent_items_limit


# Global config instance (backward compatibility)
config = Config()

# Export raw OmegaConf config for direct access
__all__ = ["cfg", "config", "Config"]
