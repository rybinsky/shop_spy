"""
ShopSpy - Price Analyzer Service

Analyzes price history to detect good deals, fake discounts, and provide recommendations.
"""

import logging
from typing import Optional

from backend.config import config

logger = logging.getLogger(__name__)


class PriceAnalyzer:
    """Service for analyzing price history and detecting deals."""

    @property
    def good_deal_threshold(self) -> float:
        return config.price_analysis.good_deal_threshold

    @property
    def overpriced_threshold(self) -> float:
        return config.price_analysis.overpriced_threshold

    @property
    def fake_discount_threshold(self) -> float:
        return config.price_analysis.fake_discount_threshold

    @property
    def min_price_margin(self) -> float:
        return config.price_analysis.min_price_margin

    @property
    def max_price_margin(self) -> float:
        return config.price_analysis.max_price_margin

    def analyze(self, history: list[dict]) -> dict:
        """
        Analyze price history and return a verdict.

        Args:
            history: List of price history entries

        Returns:
            Dictionary with analysis results:
            - verdict: good_deal, overpriced, fake_discount, normal, insufficient_data
            - message: Human-readable analysis message
            - current_price, min_price, max_price, avg_price: Price statistics
        """
        if not history or len(history) < 2:
            return self._insufficient_data()

        valid_history = [entry for entry in history if entry.get("price") is not None]
        if len(valid_history) < 2:
            return self._insufficient_data()

        prices = [entry["price"] for entry in valid_history]
        current_entry = valid_history[-1]
        current_price = current_entry["price"]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)

        # Get card prices if available
        card_prices: list[float] = [
            entry["card_price"]
            for entry in valid_history
            if entry.get("card_price") is not None
        ]
        current_card_price = current_entry.get("card_price")
        min_card_price = min(card_prices) if card_prices else None
        max_card_price = max(card_prices) if card_prices else None
        avg_card_price = sum(card_prices) / len(card_prices) if card_prices else None

        # Get claimed discount from last valid entry
        claimed_discount = self._calculate_claimed_discount(
            current_price, current_entry.get("original_price")
        )

        # Calculate card discount (savings with card vs regular)
        card_discount = None
        if current_card_price and current_price and current_card_price < current_price:
            card_discount = round((1 - current_card_price / current_price) * 100)

        # Calculate real discounts
        real_discount_from_max = self._calculate_discount(current_price, max_price)
        real_discount_from_avg = self._calculate_discount(current_price, avg_price)

        # Determine verdict
        verdict, message = self._determine_verdict(
            current_price=current_price,
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            claimed_discount=claimed_discount,
            real_discount_from_avg=real_discount_from_avg,
            price_count=len(valid_history),
            current_card_price=current_card_price,
            min_card_price=min_card_price,
        )

        # Calculate advanced metrics
        trend, trend_message = self._calculate_trend(prices)
        recommendation, recommendation_message = self._calculate_recommendation(
            current_price, min_price, max_price, avg_price, trend
        )
        value_index = self._calculate_value_index(
            current_price, min_price, max_price, avg_price
        )
        price_changes = self._calculate_price_changes(prices)
        volatility = self._calculate_volatility(prices, avg_price)

        result = {
            "verdict": verdict,
            "message": message,
            "current_price": round(current_price, 2),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "avg_price": round(avg_price, 2),
            "card_price": round(current_card_price, 2) if current_card_price else None,
            "min_card_price": round(min_card_price, 2) if min_card_price else None,
            "max_card_price": round(max_card_price, 2) if max_card_price else None,
            "avg_card_price": round(avg_card_price, 2) if avg_card_price else None,
            "card_discount": card_discount,
            "claimed_discount": claimed_discount,
            "real_discount_from_max": real_discount_from_max,
            "real_discount_from_avg": real_discount_from_avg,
            # Advanced metrics
            "trend": trend,
            "trend_message": trend_message,
            "recommendation": recommendation,
            "recommendation_message": recommendation_message,
            "value_index": value_index,
            "price_changes_count": price_changes,
            "volatility": volatility,
        }

        logger.debug(
            f"Price analysis: {verdict} - current={current_price}, "
            f"min={min_price}, max={max_price}, avg={avg_price:.2f}, "
            f"trend={trend}, value_index={value_index}"
        )

        return result

    def _determine_verdict(
        self,
        current_price: float,
        min_price: float,
        max_price: float,
        avg_price: float,
        claimed_discount: Optional[int],
        real_discount_from_avg: int,
        price_count: int,
        current_card_price: Optional[float] = None,
        min_card_price: Optional[float] = None,
    ) -> tuple[str, str]:
        """Determine the verdict based on price analysis."""
        # Check card price first
        if current_card_price:
            if min_card_price and current_card_price == min_card_price:
                return (
                    "good_deal",
                    f"✅ Лучшая цена по карте! {current_card_price:,.0f} ₽",
                )
            if current_card_price <= min_price:
                return (
                    "good_deal",
                    f"✅ Отличная цена по карте: {current_card_price:,.0f} ₽!",
                )
            if min_card_price and current_card_price <= min_card_price * (
                1 + self.min_price_margin
            ):
                return (
                    "good_deal",
                    f"✅ Цена по карте близка к минимуму ({min_card_price:,.0f} ₽).",
                )

        # Best possible regular price
        if current_price == min_price:
            return (
                "good_deal",
                f"✅ Это лучшая цена за период! Минимум: {min_price:,.0f} ₽",
            )

        # Close to minimum
        if current_price <= min_price * (1 + self.min_price_margin):
            return (
                "good_deal",
                f"✅ Цена близка к минимуму ({min_price:,.0f} ₽). Хорошее предложение!",
            )

        # Close to maximum
        if current_price >= max_price * self.max_price_margin:
            return (
                "overpriced",
                f"⚠️ Цена близка к максимуму ({max_price:,.0f} ₽). Лучше подождать.",
            )

        # Fake discount detection
        if (
            claimed_discount
            and claimed_discount >= self.fake_discount_threshold * 100
            and current_price > avg_price
        ):
            return (
                "fake_discount",
                f"🚨 Фейковая скидка! Заявлено −{claimed_discount}%, "
                f"но раньше было дешевле ({min_price:,.0f} ₽).",
            )

        # Good real discount from average
        if real_discount_from_avg >= 10:
            return (
                "good_deal",
                f"✅ Реальная скидка {real_discount_from_avg}% от средней цены!",
            )

        # Normal price
        return (
            "normal",
            f"ℹ️ Обычная цена. Средняя: {avg_price:,.0f} ₽, минимум: {min_price:,.0f} ₽",
        )

    def _calculate_claimed_discount(
        self, current_price: float, original_price: Optional[float]
    ) -> Optional[int]:
        """Calculate the discount claimed by the seller."""
        if not original_price or original_price <= current_price:
            return None
        discount = round((1 - current_price / original_price) * 100)
        return discount if discount > 0 else None

    def _calculate_discount(self, current_price: float, reference_price: float) -> int:
        """Calculate real discount from a reference price."""
        if reference_price <= 0:
            return 0
        return round((1 - current_price / reference_price) * 100)

    def _calculate_trend(self, prices: list[float]) -> tuple[str, str]:
        """Calculate price trend based on recent history."""
        if len(prices) < 3:
            return "stable", "➡️ Недостаточно данных для определения тренда"

        # Compare last third vs first third
        third = len(prices) // 3
        first_avg = sum(prices[:third]) / third if third > 0 else prices[0]
        last_avg = sum(prices[-third:]) / third if third > 0 else prices[-1]

        # Also check last 3-5 points for short-term trend
        recent = prices[-min(5, len(prices)) :]
        recent_trend = (
            sum(recent[-2:]) / 2 - sum(recent[:2]) / 2 if len(recent) >= 2 else 0
        )

        change_percent = (
            ((last_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0
        )

        if change_percent > 5:
            return "rising", f"📈 Цена растёт (+{change_percent:.0f}% за период)"
        elif change_percent < -5:
            return "falling", f"📉 Цена падает ({change_percent:.0f}% за период)"
        elif recent_trend > 0:
            return "rising_slightly", "↗️ Небольшой рост в последнее время"
        elif recent_trend < 0:
            return "falling_slightly", "↘️ Небольшое снижение в последнее время"
        else:
            return "stable", "➡️ Цена стабильна"

    def _calculate_recommendation(
        self,
        current_price: float,
        min_price: float,
        max_price: float,
        avg_price: float,
        trend: str,
    ) -> tuple[str, str]:
        """Calculate purchase recommendation."""
        # Price position relative to range
        price_range = max_price - min_price
        if price_range > 0:
            position = (current_price - min_price) / price_range
        else:
            position = 0.5

        # Good price if in bottom 20% of range
        if position <= 0.2:
            if trend in ["falling", "falling_slightly"]:
                return "good_price", "🔥 Отличная цена! Можно брать."
            return "buy_now", "✅ Хорошая цена, рекомендую к покупке."

        # Bad price if in top 30%
        if position >= 0.7:
            if trend in ["falling", "falling_slightly"]:
                return "wait", "⏳ Цена высокая, но падает. Подождите немного."
            return "wait", "⏠ Цена завышена. Лучше подождать снижения."

        # Middle range
        if trend in ["falling", "falling_slightly"]:
            return "wait", "📉 Цена падает. Подождите для лучшей сделки."
        elif trend in ["rising", "rising_slightly"]:
            return "buy_soon", "📈 Цена растёт. Если нужно — берите сейчас."
        else:
            return "neutral", "ℹ️ Обычная цена. Можете подождать или брать."

    def _calculate_value_index(
        self,
        current_price: float,
        min_price: float,
        max_price: float,
        avg_price: float,
    ) -> int:
        """Calculate value index (0-100) where 100 is the best deal."""
        if max_price == min_price:
            return 50  # No price variation

        # How close to minimum (0-60 points)
        min_score = 60 * (1 - (current_price - min_price) / (max_price - min_price))

        # How close to average (0-30 points)
        if current_price <= avg_price:
            avg_score = 30 * (1 - (avg_price - current_price) / avg_price)
        else:
            avg_score = 0

        # Bonus for being below average (0-10 points)
        below_avg_bonus = 10 if current_price < avg_price else 0

        total = min(100, max(0, int(min_score + avg_score + below_avg_bonus)))
        return total

    def _calculate_price_changes(self, prices: list[float]) -> int:
        """Count number of significant price changes."""
        if len(prices) < 2:
            return 0

        changes = 0
        for i in range(1, len(prices)):
            if prices[i] != prices[i - 1]:
                changes += 1
        return changes

    def _calculate_volatility(self, prices: list[float], avg_price: float) -> str:
        """Calculate price volatility level."""
        if len(prices) < 2 or avg_price == 0:
            return "unknown"

        # Calculate standard deviation
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        std_dev = variance**0.5
        coefficient_of_variation = (std_dev / avg_price) * 100

        if coefficient_of_variation < 5:
            return "low"
        elif coefficient_of_variation < 15:
            return "medium"
        else:
            return "high"

    def _insufficient_data(self) -> dict:
        """Return result for insufficient data case."""
        return {
            "verdict": "insufficient_data",
            "message": "📊 Недостаточно данных для анализа. Посещайте товар чаще!",
            "current_price": None,
            "min_price": None,
            "max_price": None,
            "avg_price": None,
            "card_price": None,
            "min_card_price": None,
            "max_card_price": None,
            "avg_card_price": None,
            "card_discount": None,
            "claimed_discount": None,
            "real_discount_from_max": None,
            "real_discount_from_avg": None,
            "trend": "stable",
            "trend_message": "➡️ Недостаточно данных",
            "recommendation": "neutral",
            "recommendation_message": "ℹ️ Нужны данные для рекомендации",
            "value_index": 50,
            "price_changes_count": 0,
            "volatility": "unknown",
        }

    def should_notify(
        self,
        new_price: float,
        old_price: float,
        target_price: Optional[float] = None,
    ) -> tuple[bool, str]:
        """Determine if user should be notified about price change."""
        if new_price < old_price:
            if target_price and new_price <= target_price:
                return True, "target_reached"
            drop_percent = (old_price - new_price) / old_price * 100
            if drop_percent >= config.price_analysis.notify_drop_percent:
                return True, "price_dropped"

        if new_price > old_price * (
            1 + config.price_analysis.notify_rise_percent / 100
        ):
            return True, "price_increased"

        return False, "no_significant_change"
