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
            history: List of price history entries with 'price', 'original_price', 'card_price', 'recorded_at'

        Returns:
            Dictionary with analysis results:
            - verdict: good_deal, overpriced, fake_discount, normal, insufficient_data
            - message: Human-readable analysis message
            - current_price, min_price, max_price, avg_price: Price statistics
            - card_price, min_card_price, avg_card_price: Card price statistics (if available)
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

        # Get card prices if available
        card_prices: list[float] = [
            h["card_price"] for h in history if h.get("card_price") is not None
        ]
        current_card_price = history[-1].get("card_price")
        min_card_price = min(card_prices) if card_prices else None
        max_card_price = max(card_prices) if card_prices else None
        avg_card_price = sum(card_prices) / len(card_prices) if card_prices else None

        # Get claimed discount from last entry
        current_entry = history[-1]
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
            price_count=len(prices),
            current_card_price=current_card_price,
            min_card_price=min_card_price,
        )

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
        }

        logger.debug(
            f"Price analysis: {verdict} - current={current_price}, "
            f"min={min_price}, max={max_price}, avg={avg_price:.2f}"
            + (f", card={current_card_price}" if current_card_price else "")
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
        """
        Determine the verdict based on price analysis.

        Returns:
            Tuple of (verdict, message)
        """
        # Check card price first (it's the best deal if available)
        if current_card_price:
            if min_card_price and current_card_price == min_card_price:
                return (
                    "good_deal",
                    f"✅ Лучшая цена по карте! {current_card_price:,.0f} ₽ (минимум за период)",
                )
            if current_card_price <= min_price:
                return (
                    "good_deal",
                    f"✅ Отличная цена по карте: {current_card_price:,.0f} ₽! "
                    f"Обычная: {current_price:,.0f} ₽",
                )
            if min_card_price and current_card_price <= min_card_price * 1.05:
                return (
                    "good_deal",
                    f"✅ Цена по карте близка к минимуму ({min_card_price:,.0f} ₽). "
                    f"Сейчас: {current_card_price:,.0f} ₽",
                )

        # Best possible regular price
        if current_price == min_price:
            card_msg = (
                f" По карте: {current_card_price:,.0f} ₽" if current_card_price else ""
            )
            return (
                "good_deal",
                f"✅ Это лучшая цена за весь период! Минимум: {min_price:,.0f} ₽{card_msg}",
            )

        # Close to minimum (within 5%)
        if current_price <= min_price * 1.05:
            card_msg = (
                f" По карте ещё дешевле: {current_card_price:,.0f} ₽"
                if current_card_price
                else ""
            )
            return (
                "good_deal",
                f"✅ Цена близка к минимуму ({min_price:,.0f} ₽). Хорошее предложение!{card_msg}",
            )

        # Close to maximum (within 5%)
        if current_price >= max_price * 0.95:
            card_hint = (
                f" 💳 С картой дешевле: {current_card_price:,.0f} ₽"
                if current_card_price and current_card_price < current_price
                else ""
            )
            return (
                "overpriced",
                f"⚠️ Цена близка к максимуму ({max_price:,.0f} ₽). "
                f"Лучше подождать снижения.{card_hint}",
            )

        # Fake discount detection
        if (
            claimed_discount
            and claimed_discount >= self.FAKE_DISCOUNT_THRESHOLD * 100
            and current_price > avg_price
        ):
            card_hint = (
                f" 💳 По карте: {current_card_price:,.0f} ₽"
                if current_card_price
                else ""
            )
            return (
                "fake_discount",
                f"🚨 Фейковая скидка! Заявлено −{claimed_discount}%, "
                f"но раньше было дешевле ({min_price:,.0f} ₽). "
                f"Средняя: {avg_price:,.0f} ₽{card_hint}",
            )

        # Good real discount from average
        if real_discount_from_avg >= 10:
            card_msg = (
                f" По карте ещё дешевле: {current_card_price:,.0f} ₽"
                if current_card_price and current_card_price < current_price
                else ""
            )
            return (
                "good_deal",
                f"✅ Реальная скидка {real_discount_from_avg}% от средней цены. Можно брать!{card_msg}",
            )

        # Normal price
        card_hint = (
            f" 💳 С картой: {current_card_price:,.0f} ₽"
            if current_card_price and current_card_price < current_price
            else ""
        )
        return (
            "normal",
            f"ℹ️ Обычная цена. Средняя: {avg_price:,.0f} ₽, минимум: {min_price:,.0f} ₽{card_hint}",
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
            "card_price": None,
            "min_card_price": None,
            "max_card_price": None,
            "avg_card_price": None,
            "card_discount": None,
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
