"""
ShopSpy - AI Analyzer Service

Handles AI-powered review analysis using Gemini (free) or Claude (paid) APIs.
"""

import hashlib
import json
import logging
from typing import Optional

import httpx

from backend.config import config

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Service for AI-powered review analysis."""

    def __init__(self):
        """Initialize AI analyzer with configuration from config.yaml."""
        pass

    @property
    def gemini_api_key(self) -> Optional[str]:
        return config.ai.gemini_api_key

    @property
    def claude_api_key(self) -> Optional[str]:
        return config.ai.claude_api_key

    @property
    def gemini_model(self) -> str:
        return config.ai.gemini_model

    @property
    def gemini_max_tokens(self) -> int:
        return config.ai.gemini_max_tokens

    @property
    def gemini_temperature(self) -> float:
        return config.ai.gemini_temperature

    @property
    def claude_model(self) -> str:
        return config.ai.claude_model

    @property
    def claude_max_tokens(self) -> int:
        return config.ai.claude_max_tokens

    @property
    def available(self) -> bool:
        """Check if any AI provider is available."""
        return bool(self.gemini_api_key or self.claude_api_key)

    @property
    def provider(self) -> Optional[str]:
        """Get the active provider (Gemini has priority as it's free)."""
        if self.gemini_api_key:
            return "gemini"
        if self.claude_api_key:
            return "claude"
        return None

    async def analyze_reviews(
        self,
        product_name: str,
        reviews: list[str],
    ) -> dict:
        """
        Analyze product reviews using AI.

        Args:
            product_name: Product name for context
            reviews: List of review texts

        Returns:
            Dictionary with analysis results:
            - pros: List of advantages
            - cons: List of disadvantages
            - fake_reviews_detected: Boolean
            - fake_reviews_reason: String or None
            - rating_honest: Float 1-5 or None
            - verdict: Short verdict
            - buy_recommendation: 'yes', 'no', 'wait', or 'unknown'
        """
        if not self.available:
            return self._no_api_key_response()

        if not reviews:
            return self._no_reviews_response()

        # Limit reviews to avoid token limits
        limited_reviews = reviews[:20]

        prompt = self._build_prompt(product_name, limited_reviews)

        try:
            if self.provider == "gemini":
                result = await self._call_gemini(prompt)
            else:
                result = await self._call_claude(prompt)

            if result:
                parsed = self._parse_response(result)
                logger.info(
                    f"AI analysis completed for '{product_name}': "
                    f"recommendation={parsed.get('buy_recommendation')}, "
                    f"rating={parsed.get('rating_honest')}"
                )
                return parsed

            return self._error_response("Empty response from AI")

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._error_response(str(e))

    def _build_prompt(self, product_name: str, reviews: list[str]) -> str:
        """Build the analysis prompt."""
        reviews_text = "\n".join(f"- {r[:500]}" for r in reviews)

        return f"""Проанализируй отзывы на товар "{product_name}" с маркетплейса.

Отзывы:
{reviews_text}

Выдели:
1. Главные плюсы (3-5 пунктов)
2. Главные минусы (3-5 пунктов)
3. Есть ли признаки накрученных отзывов (однотипные, только положительные, странные аккаунты)
4. Честный рейтинг от 1 до 5 (с учётом накрутки если есть)
5. Краткий вердикт: стоит ли покупать
6. Рекомендация: "yes" (покупать), "no" (не покупать), или "wait" (подождать)

Ответь строго в формате JSON без markdown:
{{
  "pros": ["плюс1", "плюс2", ...],
  "cons": ["минус1", "минус2", ...],
  "fake_reviews_detected": true или false,
  "fake_reviews_reason": "причина или null",
  "rating_honest": 4.2,
  "verdict": "Краткий вердикт в 1-2 предложения",
  "buy_recommendation": "yes" или "no" или "wait"
}}

Пиши "е" вместо "ё". Будь честным и критичным."""

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        """
        Call Google Gemini API.

        Args:
            prompt: Analysis prompt

        Returns:
            Response text or None
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": self.gemini_max_tokens,
                "temperature": self.gemini_temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{url}?key={self.gemini_api_key}",
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                else:
                    logger.error(
                        f"Gemini API error: {response.status_code} - {response.text[:200]}"
                    )

        except httpx.TimeoutException:
            logger.error("Gemini API timeout")
        except Exception as e:
            logger.error(f"Gemini API exception: {e}")

        return None

    async def _call_claude(self, prompt: str) -> Optional[str]:
        """
        Call Anthropic Claude API.

        Args:
            prompt: Analysis prompt

        Returns:
            Response text or None
        """
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": self.claude_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.claude_model,
            "max_tokens": self.claude_max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    content = data.get("content", [])
                    if content:
                        return content[0].get("text", "")
                else:
                    logger.error(
                        f"Claude API error: {response.status_code} - {response.text[:200]}"
                    )

        except httpx.TimeoutException:
            logger.error("Claude API timeout")
        except Exception as e:
            logger.error(f"Claude API exception: {e}")

        return None

    def _parse_response(self, text: str) -> dict:
        """
        Parse JSON response from AI.

        Args:
            text: Raw response text

        Returns:
            Parsed dictionary
        """
        try:
            # Find JSON in response
            start = text.find("{")
            end = text.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")

        # Return partial result
        return {
            "pros": [],
            "cons": [],
            "verdict": text[:200] if text else "Ошибка парсинга ответа",
            "buy_recommendation": "unknown",
            "fake_reviews_detected": False,
            "rating_honest": None,
        }

    def _no_api_key_response(self) -> dict:
        """Return response when no API key is configured."""
        return {
            "pros": ["AI-анализ недоступен"],
            "cons": ["Настройте GEMINI_API_KEY или ANTHROPIC_API_KEY"],
            "verdict": "Для AI-анализа отзывов добавьте API ключ в настройках",
            "buy_recommendation": "unknown",
            "fake_reviews_detected": False,
            "rating_honest": None,
        }

    def _no_reviews_response(self) -> dict:
        """Return response when no reviews provided."""
        return {
            "pros": [],
            "cons": [],
            "verdict": "Нет отзывов для анализа",
            "buy_recommendation": "unknown",
            "fake_reviews_detected": False,
            "rating_honest": None,
        }

    def _error_response(self, error: str) -> dict:
        """Return error response."""
        return {
            "pros": [],
            "cons": [],
            "verdict": f"Ошибка AI-анализа: {error}",
            "buy_recommendation": "unknown",
            "fake_reviews_detected": False,
            "rating_honest": None,
        }

    def get_cache_key(self, platform: str, product_id: str, reviews_count: int) -> str:
        """
        Generate cache key for review analysis.

        Args:
            platform: Platform identifier
            product_id: Product ID
            reviews_count: Number of reviews

        Returns:
            Cache key string
        """
        data = f"{platform}:{product_id}:{reviews_count}"
        return hashlib.md5(data.encode()).hexdigest()
