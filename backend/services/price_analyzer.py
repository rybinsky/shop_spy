"""
ShopSpy - Price Analyzer Service

Analyzes price history to detect good deals, fake discounts, and provide recommendations.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PriceAnalyzer:
    """Service for analyzing price history and detecting deals."""

    # Thresholds for analysis
    GOOD_DEAL_THRESHOLD = 0.85  # 15% below average
    OVERPRICED_THRESHOLD = 1.10  # 10% above average
    FAKE_DISCOUNT_THRESHOLD = 0.30  # 30% claimed discount triggers check

    def analyze(self, history: list[dict]) -> dict:
        """
        Analyze price history and return a verdict.

        Args:
            history: List of price history entries with 'price', 'original_price', 'recorded_at'

        Returns:
            Dictionary with analysis results:
            - verdict: good_deal, overpriced, fake_discount, normal, insufficient_data
            - message: Human-readable analysis message
            - current_price, min_price, max_price, avg_price: Price statistics
            - claimed_discount: Discount claimed by seller
            - real_discount_from_max: Real discount from max price
            - real_discount_from_avg: Real discount from average price
        """
        if not history or len(history) < 2:
            return self._insufficient_data()

        prices = [h["price"] for h in history]
        current_price = prices[-1]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)

        # Get claimed discount from last entry
        current_entry = history[-1]
        claimed_discount = self._calculate_claimed_discount(
            current_price, current_entry.get("original_price")
        )

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
            price_count=len(prices),
        )

        result = {
            "verdict": verdict,
            "message": message,
            "current_price": round(current_price, 2),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "avg_price": round(avg_price, 2),
            "claimed_discount": claimed_discount,
            "real_discount_from_max": real_discount_from_max,
            "real_discount_from_avg": real_discount_from_avg,
        }

        logger.debug(
            f"Price analysis: {verdict} - current={current_price}, "
            f"min={min_price}, max={max_price}, avg={avg_price:.2f}"
        )

        return result

    def _determine_verdict(
        self,
        current_price: float,
        min_price: float,
        max_price: float,
        avg_price: float,
        claimed_discount: int,
        real_discount_from_avg: int,
        price_count: int,
    ) -> tuple[str, str]:
        """
        Determine the verdict based on price analysis.

        Returns:
            Tuple of (verdict, message)
        """
        # Best possible price
        if current_price == min_price:
            return (
                "good_deal",
                f"✅ Это лучшая цена за весь период наблюдения! Минимум: {min_price:,.0f} ₽",
            )

        # Close to minimum (within 5%)
        if current_price <= min_price * 1.05:
            return (
                "good_deal",
                f"✅ Цена близка к минимуму ({min_price:,.0f} ₽). Хорошее предложение!",
            )

        # Close to maximum (within 5%)
        if current_price >= max_price * 0.95:
            return (
                "overpriced",
                f"⚠️ Цена близка к максимуму ({max_price:,.0f} ₽). Лучше подождать снижения.",
            )

        # Fake discount detection
        if (
            claimed_discount
            and claimed_discount >= self.FAKE_DISCOUNT_THRESHOLD * 100
            and current_price > avg_price
        ):
            return (
                "fake_discount",
                f"🚨 Фейковая скидка! Заявлено −{claimed_discount}%, "
                f"но раньше было дешевле ({min_price:,.0f} ₽). "
                f"Средняя цена: {avg_price:,.0f} ₽",
            )

        # Good real discount from average
        if real_discount_from_avg >= 10:
            return (
                "good_deal",
                f"✅ Реальная скидка {real_discount_from_avg}% от средней цены. Можно брать!",
            )

        # Normal price
        return (
            "normal",
            f"ℹ️ Обычная цена. Средняя: {avg_price:,.0f} ₽, минимум: {min_price:,.0f} ₽",
        )

    def _calculate_claimed_discount(
        self, current_price: float, original_price: Optional[float]
    ) -> Optional[int]:
        """
        Calculate the discount claimed by the seller.

        Args:
            current_price: Current price
            original_price: Original price before discount

        Returns:
            Discount percentage or None
        """
        if not original_price or original_price <= current_price:
            return None

        discount = round((1 - current_price / original_price) * 100)
        return discount if discount > 0 else None

    def _calculate_discount(self, current_price: float, reference_price: float) -> int:
        """
        Calculate real discount from a reference price.

        Args:
            current_price: Current price
            reference_price: Reference price (max or average)

        Returns:
            Discount percentage (can be negative if price is higher)
        """
        if reference_price <= 0:
            return 0

        discount = round((1 - current_price / reference_price) * 100)
        return discount

    def _insufficient_data(self) -> dict:
        """Return result for insufficient data case."""
        return {
            "verdict": "insufficient_data",
            "message": "📊 Недостаточно данных для анализа. Посещайте товар чаще для накопления истории цен!",
            "current_price": None,
            "min_price": None,
            "max_price": None,
            "avg_price": None,
            "claimed_discount": None,
            "real_discount_from_max": None,
            "real_discount_from_avg": None,
        }

    def should_notify(
        self,
        new_price: float,
        old_price: float,
        target_price: Optional[float] = None,
    ) -> tuple[bool, str]:
        """
        Determine if user should be notified about price change.

        Args:
            new_price: New price
            old_price: Previous price
            target_price: User's target price (optional)

        Returns:
            Tuple of (should_notify, reason)
        """
        # Price dropped
        if new_price < old_price:
            # Target price reached
            if target_price and new_price <= target_price:
                return True, "target_reached"

            # Significant drop (more than 5%)
            drop_percent = (old_price - new_price) / old_price * 100
            if drop_percent >= 5:
                return True, "price_dropped"

        # Price increased significantly
        if new_price > old_price * 1.1:
            return True, "price_increased"

        return False, "no_significant_change"
