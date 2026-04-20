/**
 * ShopSpy - Общий модуль для content-скриптов
 * Единый UI, API-вызовы, логика для WB и Ozon
 */

const SHOPSPY = {
  API_BASE: SHOPSPY_CONFIG.API_BASE,
  panelCreated: false,
  currentProductId: null,
  currentPlatform: null,
  historyData: null,
  analysisData: null,
  isTracking: null,
  trackingChatId: null,

  // ── API ──

  async sendPrice(platform, productId, name, price, originalPrice, cardPrice) {
    try {
      await fetch(`${this.API_BASE}/api/price`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platform,
          product_id: productId,
          product_name: name,
          price,
          original_price: originalPrice,
          card_price: cardPrice,
          url: window.location.href,
        }),
      });
    } catch (e) {
      console.log("ShopSpy: сервер недоступен", e.message);
    }
  },

  /**
   * Отправляет событие просмотра товара в user_stats.
   *
   * Особенности:
   * - не падает если пользователь не авторизован (telegram_id отсутствует)
   * - анти-спам: не чаще 1 раза на товар за 30 минут
   */
  async sendView(
    platform,
    productId,
    productName,
    price,
    originalPrice,
    cardPrice,
    avgPrice,
  ) {
    const telegramId = await this.getTelegramId();
    if (!telegramId) return;

    const THROTTLE_MS = 30 * 60 * 1000;
    const key = `shopspy_view_sent_${telegramId}_${platform}_${productId}`;

    try {
      const last = Number(localStorage.getItem(key) || "0");
      if (last && Date.now() - last < THROTTLE_MS) return;

      await fetch(`${this.API_BASE}/api/stats/view`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          telegram_id: telegramId,
          platform,
          product_id: productId,
          product_name: productName,
          price,
          card_price: cardPrice,
          avg_price: avgPrice,
          original_price: originalPrice,
        }),
      });

      localStorage.setItem(key, String(Date.now()));
    } catch (e) {
      // не шумим, чтобы не мешать пользователю
      console.log(
        "ShopSpy: не удалось отправить статистику просмотра",
        e.message,
      );
    }
  },

  async getHistory(platform, productId) {
    try {
      const r = await fetch(
        `${this.API_BASE}/api/price/history?platform=${platform}&product_id=${productId}`,
      );

      if (!r.ok) {
        const errorMsg =
          r.status === 429
            ? "Превышен лимит запросов. Попробуйте позже."
            : r.status >= 500
              ? "Ошибка сервера. Попробуйте позже."
              : `Ошибка: ${r.status}`;
        return {
          history: [],
          analysis: {
            verdict: "error",
            message: errorMsg,
          },
        };
      }

      return await r.json();
    } catch (e) {
      return {
        history: [],
        analysis: {
          verdict: "error",
          message: "Сервер недоступен. Проверьте подключение.",
        },
      };
    }
  },

  async analyzeReviews(platform, productId, name, reviews) {
    try {
      const r = await fetch(`${this.API_BASE}/api/reviews/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platform,
          product_id: productId,
          product_name: name,
          reviews,
        }),
      });

      if (!r.ok) {
        const errorMsg =
          r.status === 429
            ? "Превышен лимит AI-запросов. Попробуйте завтра."
            : r.status >= 500
              ? "Ошибка сервера. Попробуйте позже."
              : `Ошибка: ${r.status}`;
        return {
          summary: {
            pros: [],
            cons: [],
            fake_reviews_detected: false,
            verdict: errorMsg,
            buy_recommendation: "unknown",
          },
        };
      }

      return await r.json();
    } catch (e) {
      return {
        summary: {
          pros: [],
          cons: [],
          fake_reviews_detected: false,
          verdict: "Сервер недоступен. Проверьте подключение.",
          buy_recommendation: "unknown",
        },
      };
    }
  },

  // ── Tracking API ──

  async getTelegramId() {
    return new Promise((resolve) => {
      chrome.storage.local.get(["telegram_id"], (result) => {
        resolve(result.telegram_id);
      });
    });
  },

  async checkTracking(platform, productId) {
    const chatId = await this.getTelegramId();
    if (!chatId) return { tracking: false, chatId: null };

    try {
      const r = await fetch(`${this.API_BASE}/api/alerts?chat_id=${chatId}`);
      const data = await r.json();
      const isTracking =
        data.alerts?.some(
          (a) => a.platform === platform && a.product_id === productId,
        ) || false;
      return { tracking: isTracking, chatId };
    } catch (e) {
      console.log("ShopSpy: ошибка проверки отслеживания", e.message);
      return { tracking: false, chatId };
    }
  },

  async toggleTracking(
    platform,
    productId,
    productName,
    url,
    isCurrentlyTracking,
  ) {
    const chatId = await this.getTelegramId();
    if (!chatId) {
      return { error: "not_authenticated" };
    }

    try {
      if (isCurrentlyTracking) {
        await fetch(
          `${this.API_BASE}/api/alerts?chat_id=${chatId}&platform=${platform}&product_id=${productId}`,
          {
            method: "DELETE",
          },
        );
        return { tracking: false };
      } else {
        await fetch(`${this.API_BASE}/api/alerts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: chatId,
            platform,
            product_id: productId,
            product_name: productName,
            url,
          }),
        });
        return { tracking: true };
      }
    } catch (e) {
      console.log("ShopSpy: ошибка переключения отслеживания", e.message);
      return { error: "network_error" };
    }
  },

  // ── UI: Создание панели ──

  createPanel() {
    if (this.panelCreated) return;

    const panel = document.createElement("div");
    panel.id = "shopspy-panel";
    panel.className = "shopspy-panel";
    panel.innerHTML = `
      <div class="shopspy-header" id="shopspy-toggle">
        <div class="shopspy-logo">
          <span class="shopspy-logo-icon">🔍</span>
          <span>ShopSpy</span>
        </div>
        <div style="display:flex;gap:6px;align-items:center;">
          <button class="shopspy-close" id="shopspy-collapse" title="Свернуть">−</button>
        </div>
      </div>
      <div class="shopspy-body" id="shopspy-body">
        <div class="shopspy-loader"><div class="shopspy-spinner"></div> Анализирую товар...</div>
      </div>
    `;
    document.body.appendChild(panel);
    this.panelCreated = true;

    document
      .getElementById("shopspy-collapse")
      .addEventListener("click", (e) => {
        e.stopPropagation();
        panel.classList.toggle("collapsed");
      });
    document.getElementById("shopspy-toggle").addEventListener("click", () => {
      if (panel.classList.contains("collapsed"))
        panel.classList.remove("collapsed");
    });
  },

  // ── UI: Рендер контента ──

  renderPanel(data) {
    const body = document.getElementById("shopspy-body");
    if (!body) return;

    const {
      history,
      analysis,
      reviews,
      productName,
      price,
      originalPrice,
      cardPrice,
      platform,
      productId,
    } = data;

    // Название карты/кошелька в зависимости от платформы
    const cardName = platform === "wb" ? "WB Кошелёк" : "Ozon Банк";
    const cardEmoji = platform === "wb" ? "💰" : "💳";
    // Цвета для карты/кошелька (WB - светло-фиолетовый как лого, Ozon - синий)
    const cardBadgeBg =
      platform === "wb"
        ? "background:linear-gradient(135deg,#a855f7,#c084fc)"
        : "background:linear-gradient(135deg,#00f,#8b5cf6)";
    const cardPriceColor = platform === "wb" ? "#c084fc" : "#a78bfa";
    const cardBadgeBgRgba =
      platform === "wb" ? "rgba(192,132,252,0.1)" : "rgba(167,139,250,0.1)";
    const cardBadgeBorderRgba =
      platform === "wb" ? "rgba(192,132,252,0.3)" : "rgba(167,139,250,0.3)";
    const cardBadgeTextRgba = platform === "wb" ? "#e9d5ff" : "#c4b5fd";
    const icons = {
      good_deal: "✅",
      fake_discount: "🚨",
      overpriced: "⚠️",
      normal: "ℹ️",
      insufficient_data: "📊",
      error: "❌",
    };

    let html = "";

    const formatMoney = (value) =>
      value || value === 0
        ? `${Math.round(value).toLocaleString("ru")} ₽`
        : "—";
    const formatPercent = (value) =>
      value || value === 0 ? `${value > 0 ? "+" : ""}${value}%` : "—";
    const safeNumber = (value) => (value || value === 0 ? Number(value) : null);
    const clamp = (value, minValue, maxValue) =>
      Math.min(Math.max(value, minValue), maxValue);
    const buildMarker = (label, value, modifier = "") => {
      if (value === null || value === undefined) return "";
      return `<div class="shopspy-range-marker ${modifier}" style="left:${value}%;">${label}</div>`;
    };

    // New backend analysis metrics
    const backendTrend = analysis.trend || "stable";
    const backendTrendMessage = analysis.trend_message || "";
    const backendRecommendation = analysis.recommendation || "neutral";
    const backendRecommendationMessage = analysis.recommendation_message || "";
    const valueIndex = analysis.value_index ?? 50;
    const priceChangesCount = analysis.price_changes_count ?? 0;
    const volatility = analysis.volatility || "unknown";

    // Value index color based on score
    const getValueIndexColor = (index) => {
      if (index >= 80) return "#4ade80"; // green - excellent
      if (index >= 60) return "#a3e635"; // lime - good
      if (index >= 40) return "#facc15"; // yellow - neutral
      if (index >= 20) return "#fb923c"; // orange - not great
      return "#ef4444"; // red - bad
    };
    const valueIndexColor = getValueIndexColor(valueIndex);

    const prices = (history || [])
      .map((h) => safeNumber(h.price))
      .filter((value) => value !== null);
    const cardHistory = (history || []).filter(
      (h) => h.card_price !== null && h.card_price !== undefined,
    );
    const cardPrices = cardHistory
      .map((h) => safeNumber(h.card_price))
      .filter((value) => value !== null);
    const allValues = [...prices, ...cardPrices];
    const hasHistory = prices.length > 1;
    const minPrice =
      safeNumber(analysis.min_price) ??
      (allValues.length ? Math.min(...allValues) : null);
    const maxPrice =
      safeNumber(analysis.max_price) ??
      (allValues.length ? Math.max(...allValues) : null);
    const avgPrice =
      safeNumber(analysis.avg_price) ??
      (prices.length
        ? Math.round(
            prices.reduce((sum, value) => sum + value, 0) / prices.length,
          )
        : null);
    const currentPrice =
      safeNumber(price) ?? safeNumber(analysis.current_price);
    const currentCardPrice =
      safeNumber(cardPrice) ?? safeNumber(analysis.card_price);
    const currentRangeValue = currentCardPrice ?? currentPrice;
    const range =
      minPrice !== null && maxPrice !== null
        ? Math.max(maxPrice - minPrice, 1)
        : 1;
    const currentPosition =
      currentRangeValue !== null && minPrice !== null && maxPrice !== null
        ? clamp(((currentRangeValue - minPrice) / range) * 100, 0, 100)
        : null;
    const regularPosition =
      currentPrice !== null && minPrice !== null && maxPrice !== null
        ? clamp(((currentPrice - minPrice) / range) * 100, 0, 100)
        : null;
    const averagePosition =
      avgPrice !== null && minPrice !== null && maxPrice !== null
        ? clamp(((avgPrice - minPrice) / range) * 100, 0, 100)
        : null;
    const cardPosition =
      currentCardPrice !== null && minPrice !== null && maxPrice !== null
        ? clamp(((currentCardPrice - minPrice) / range) * 100, 0, 100)
        : null;

    const discountFromOriginal =
      currentPrice && originalPrice && originalPrice > currentPrice
        ? Math.round((1 - currentPrice / originalPrice) * 100)
        : null;
    const cardDiscount =
      currentCardPrice && originalPrice && originalPrice > currentCardPrice
        ? Math.round((1 - currentCardPrice / originalPrice) * 100)
        : null;
    const cardVsRegularAmount =
      currentPrice && currentCardPrice && currentCardPrice < currentPrice
        ? Math.round(currentPrice - currentCardPrice)
        : null;
    const cardVsRegularPercent =
      currentPrice && currentCardPrice && currentCardPrice < currentPrice
        ? Math.round((1 - currentCardPrice / currentPrice) * 100)
        : null;
    const deltaToMinPercent =
      currentRangeValue && minPrice
        ? Math.round(((currentRangeValue - minPrice) / minPrice) * 100)
        : null;
    const deltaToAvgPercent =
      currentRangeValue && avgPrice
        ? Math.round(((currentRangeValue - avgPrice) / avgPrice) * 100)
        : null;
    const trendPercent =
      prices.length >= 2 && prices[0] > 0
        ? Math.round(
            ((prices[prices.length - 1] - prices[0]) / prices[0]) * 100,
          )
        : null;
    const confidenceLabel =
      prices.length >= 10
        ? "высокая"
        : prices.length >= 5
          ? "средняя"
          : "низкая";
    const cardNameInstrument = cardName
      .replace("Кошелёк", "кошельком")
      .replace("Банк", "картой");

    const getHeroMeta = () => {
      const verdict = analysis.verdict;
      if (verdict === "fake_discount") {
        return {
          title: "Осторожно со скидкой",
          subtitle: "Заявленная выгода выглядит слабее реальной истории цены.",
        };
      }
      if (currentCardPrice && currentPrice && currentCardPrice < currentPrice) {
        if (verdict === "good_deal") {
          return {
            title: "Выгодно только по карте",
            subtitle: `Обычная цена выглядит заметно слабее, чем предложение с ${cardNameInstrument}.`,
          };
        }
        return {
          title: "Есть смысл смотреть цену по карте",
          subtitle: `С ${cardNameInstrument} цена лучше обычной на ${formatMoney(cardVsRegularAmount)}.`,
        };
      }
      if (verdict === "good_deal") {
        return {
          title: "Хороший момент",
          subtitle:
            "Цена находится в нижней части диапазона за период наблюдения.",
        };
      }
      if (verdict === "overpriced") {
        return {
          title: "Лучше подождать",
          subtitle:
            "Сейчас цена выглядит высокой относительно недавней истории.",
        };
      }
      if (verdict === "insufficient_data") {
        return {
          title: "Пока мало данных",
          subtitle:
            "Нужно накопить ещё несколько наблюдений, чтобы совет был увереннее.",
        };
      }
      return {
        title: "Цена без резких сигналов",
        subtitle:
          "Сейчас товар выглядит ближе к обычному диапазону, чем к явной выгоде.",
      };
    };

    const heroMeta = getHeroMeta();
    const insightItems = [];

    if (deltaToMinPercent !== null) {
      insightItems.push({
        label: "К минимуму",
        value:
          deltaToMinPercent <= 0
            ? "на минимуме"
            : `+${deltaToMinPercent}% от минимума`,
      });
    }
    if (deltaToAvgPercent !== null) {
      insightItems.push({
        label: "К средней",
        value:
          deltaToAvgPercent < 0
            ? `${deltaToAvgPercent}% ниже средней`
            : deltaToAvgPercent > 0
              ? `+${deltaToAvgPercent}% выше средней`
              : "на уровне средней",
      });
    }
    if (trendPercent !== null) {
      const trendText =
        trendPercent < 0
          ? `↓ ${Math.abs(trendPercent)}% за период`
          : trendPercent > 0
            ? `↑ ${trendPercent}% за период`
            : "≈ без заметного тренда";
      insightItems.push({ label: "Тренд", value: trendText });
    }
    if (cardVsRegularAmount) {
      insightItems.push({
        label: cardName,
        value: `экономия ${formatMoney(cardVsRegularAmount)} (${cardVsRegularPercent}%)`,
      });
    }

    // Value Index visualization
    const valueIndexHtml = `<div class="shopspy-value-index">
      <div class="shopspy-value-index-header">
        <span class="shopspy-value-index-label">Индекс выгодности</span>
        <span class="shopspy-value-index-score" style="color:${valueIndexColor};">${valueIndex}/100</span>
      </div>
      <div class="shopspy-value-index-bar">
        <div class="shopspy-value-index-fill" style="width:${valueIndex}%;background:${valueIndexColor};"></div>
      </div>
      <div class="shopspy-value-index-hint">${backendRecommendationMessage || "Анализ цены относительно истории"}</div>
    </div>`;

    html += `<div class="shopspy-section">
      <div class="shopspy-price-hero ${analysis.verdict}">
        <div class="shopspy-price-hero-top">
          <div>
            <div class="shopspy-price-hero-label">${icons[analysis.verdict] || "ℹ️"} Решение по цене</div>
            <div class="shopspy-price-hero-title">${heroMeta.title}</div>
            <div class="shopspy-price-hero-subtitle">${heroMeta.subtitle}</div>
          </div>
          <div class="shopspy-price-hero-confidence">${prices.length || 0} точек<br><span>${confidenceLabel} уверенность</span></div>
        </div>
        ${valueIndexHtml}
        <div class="shopspy-price-facts">
          ${insightItems
            .slice(0, 3)
            .map(
              (item) => `
            <div class="shopspy-price-fact">
              <div class="shopspy-price-fact-label">${item.label}</div>
              <div class="shopspy-price-fact-value">${item.value}</div>
            </div>`,
            )
            .join("")}
        </div>
        <div class="shopspy-price-hero-note">${analysis.message}</div>
        ${backendTrendMessage ? `<div class="shopspy-trend-note">${backendTrendMessage}</div>` : ""}
      </div>
    </div>`;

    if (currentPrice || currentCardPrice) {
      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">💰 Текущие цены</div>
        <div class="shopspy-price-grid">`;

      if (currentPrice) {
        html += `<div class="shopspy-price-tile">
          <div class="shopspy-price-tile-label">Обычная цена</div>
          <div class="shopspy-price-tile-value">${formatMoney(currentPrice)}</div>
          <div class="shopspy-price-tile-meta">
            ${
              originalPrice && originalPrice > currentPrice
                ? `<span class="shopspy-price-old">${formatMoney(originalPrice)}</span><span class="shopspy-price-badge">−${discountFromOriginal}%</span>`
                : `<span class="shopspy-price-muted">Без явной скидки от зачёркнутой</span>`
            }
          </div>
        </div>`;
      }

      if (currentCardPrice && currentCardPrice !== currentPrice) {
        html += `<div class="shopspy-price-tile shopspy-price-tile-card">
          <div class="shopspy-price-tile-label">
            <span class="shopspy-card-chip" style="${cardBadgeBg};-webkit-background-clip:text;-webkit-text-fill-color:transparent;">${cardName}</span>
          </div>
          <div class="shopspy-price-tile-value" style="color:${cardPriceColor};">${formatMoney(currentCardPrice)}</div>
          <div class="shopspy-price-tile-meta">
            ${
              cardDiscount
                ? `<span class="shopspy-price-badge">−${cardDiscount}% от зачёркнутой</span>`
                : `<span class="shopspy-price-muted">Спеццена с ${cardNameInstrument}</span>`
            }
          </div>
        </div>`;
      }

      html += `</div>`;

      if (cardVsRegularAmount) {
        html += `<div class="shopspy-card-advantage" style="background:${cardBadgeBgRgba};border-color:${cardBadgeBorderRgba};color:${cardBadgeTextRgba};">
          <span class="shopspy-card-advantage-icon">${cardEmoji}</span>
          <span>С ${cardNameInstrument} цена ниже на <b>${formatMoney(cardVsRegularAmount)}</b> (${cardVsRegularPercent}%).</span>
        </div>`;
      }

      html += `</div>`;
    }

    if (currentPosition !== null) {
      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">🎯 Позиция цены</div>
        <div class="shopspy-range-card">
          <div class="shopspy-range-track-wrap">
            <div class="shopspy-range-track">
              <div class="shopspy-range-zone shopspy-range-zone-good"></div>
              <div class="shopspy-range-zone shopspy-range-zone-mid"></div>
              <div class="shopspy-range-zone shopspy-range-zone-risk"></div>
              ${buildMarker("Сейчас", regularPosition, "current")}
              ${
                cardPosition !== null && cardPosition !== regularPosition
                  ? buildMarker(cardName, cardPosition, "card")
                  : ""
              }
              ${buildMarker("Средняя", averagePosition, "average")}
            </div>
          </div>
          <div class="shopspy-range-legend">
            <span>Мин: <b>${formatMoney(minPrice)}</b></span>
            <span>Средняя: <b>${formatMoney(avgPrice)}</b></span>
            <span>Макс: <b>${formatMoney(maxPrice)}</b></span>
          </div>
        </div>
      </div>`;
    }

    if (hasHistory) {
      const W = 340;
      const H = 80;
      const pointsCount = prices.length;
      const pts = prices
        .map(
          (value, index) =>
            `${(index / (pointsCount - 1)) * W},${H - ((value - minPrice) / range) * (H - 10) - 5}`,
        )
        .join(" ");

      let cardPts = "";
      if (cardPrices.length > 1) {
        cardPts = cardHistory
          .map((entry, index) => {
            const x =
              cardHistory.length === 1
                ? W
                : (index / (cardHistory.length - 1)) * W;
            const y =
              H - ((entry.card_price - minPrice) / range) * (H - 10) - 5;
            return `${x},${y}`;
          })
          .join(" ");
      }

      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">📈 История цен (${history.length} точек)</div>
        <svg width="${W}" height="${H}" style="width:100%;background:rgba(255,255,255,0.03);border-radius:8px;">
          <defs>
            <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#e94560" stop-opacity="0.3"/>
              <stop offset="100%" stop-color="#e94560" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <polygon points="0,${H} ${pts} ${W},${H}" fill="url(#sg)"/>
          <polyline points="${pts}" fill="none" stroke="#e94560" stroke-width="2"/>
          ${cardPts ? `<polyline points="${cardPts}" fill="none" stroke="${cardPriceColor}" stroke-width="2" stroke-dasharray="4,2"/>` : ""}
          ${
            averagePosition !== null
              ? `<line x1="0" y1="${H - ((avgPrice - minPrice) / range) * (H - 10) - 5}"
                x2="${W}" y2="${H - ((avgPrice - minPrice) / range) * (H - 10) - 5}"
                stroke="#888" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>`
              : ""
          }
        </svg>
        <div class="shopspy-history-summary">
          <span>мин: ${formatMoney(minPrice)}</span>
          <span>сред: ${formatMoney(avgPrice)}</span>
          <span>макс: ${formatMoney(maxPrice)}</span>
        </div>
        ${
          cardPrices.length > 0
            ? `<div class="shopspy-history-legend">
                <span><span class="shopspy-history-line regular"></span>Обычная</span>
                <span><span class="shopspy-history-line card" style="background:${cardPriceColor};"></span>${cardName}</span>
              </div>`
            : ""
        }
      </div>`;

      if (currentRangeValue && avgPrice && currentRangeValue < avgPrice) {
        const savings = Math.round(avgPrice - currentRangeValue);
        html += `<div class="shopspy-section">
          <div class="shopspy-saving-banner">
            <span class="shopspy-saving-banner-icon">💸</span>
            <span>Вы экономите примерно <b>${formatMoney(savings)}</b> относительно средней цены.</span>
          </div>
        </div>`;
      }

      // Price behavior stats
      const volatilityLabels = {
        low: "стабильная",
        medium: "умеренная",
        high: "частые скачки",
        unknown: "неизвестно",
      };
      const volatilityColors = {
        low: "#4ade80",
        medium: "#facc15",
        high: "#ef4444",
        unknown: "#888",
      };
      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">📊 Статистика цены</div>
        <div class="shopspy-stats-grid">
          <div class="shopspy-stat-item">
            <div class="shopspy-stat-label">Изменений цены</div>
            <div class="shopspy-stat-value">${priceChangesCount}</div>
          </div>
          <div class="shopspy-stat-item">
            <div class="shopspy-stat-label">Волатильность</div>
            <div class="shopspy-stat-value" style="color:${volatilityColors[volatility]};">${volatilityLabels[volatility]}</div>
          </div>
          <div class="shopspy-stat-item">
            <div class="shopspy-stat-label">Тренд</div>
            <div class="shopspy-stat-value">${backendTrendMessage || "—"}</div>
          </div>
        </div>
      </div>`;
    }

    // ── Блок: Отслеживание ──
    const trackingStatus = this.isTracking;
    const isTrackingActive = trackingStatus === true;
    const trackingBtnClass = isTrackingActive
      ? "shopspy-track-btn tracking"
      : "shopspy-track-btn";
    const trackingBtnText = isTrackingActive
      ? "✓ Отслеживается"
      : "🔔 Отслеживать";
    const trackingBtnDisabled = trackingStatus === null ? "disabled" : "";

    html += `<div class="shopspy-section">
      <div class="shopspy-section-title">🔔 Отслеживание</div>
      <button class="${trackingBtnClass}" id="shopspy-track-btn" ${trackingBtnDisabled}>
        ${trackingBtnText}
      </button>
      <div id="shopspy-track-status" style="font-size:11px;color:#666;margin-top:6px;text-align:center;"></div>
    </div>`;

    // ── Блок: Сравнение площадок ──
    const otherPlatform = platform === "wb" ? "ozon" : "wb";
    const otherName = platform === "wb" ? "Ozon" : "Wildberries";
    const searchUrl =
      platform === "wb"
        ? `https://www.ozon.ru/search/?text=${encodeURIComponent(productName || "")}`
        : `https://www.wildberries.ru/catalog/0/search.aspx?search=${encodeURIComponent(productName || "")}`;

    html += `<div class="shopspy-section">
      <div class="shopspy-section-title">🔄 Сравнить цену</div>
      <a href="${searchUrl}" target="_blank" style="
        display:flex;align-items:center;justify-content:center;gap:8px;
        padding:10px;border-radius:8px;
        background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
        color:#ddd;text-decoration:none;font-size:13px;font-weight:500;
        transition:all 0.15s;cursor:pointer;
      " onmouseover="this.style.background='rgba(255,255,255,0.1)'"
         onmouseout="this.style.background='rgba(255,255,255,0.05)'">
        🔍 Найти на ${otherName}
      </a>
    </div>`;

    // ── Блок: AI-анализ отзывов ──
    if (reviews) {
      const s = reviews.summary || reviews;
      html += `<div class="shopspy-section"><div class="shopspy-section-title">🤖 AI-анализ отзывов</div>`;

      if (s.fake_reviews_detected) {
        html += `<div style="padding:8px 12px;background:rgba(233,69,96,0.15);border:1px solid rgba(233,69,96,0.3);border-radius:8px;font-size:12px;color:#ef9a9a;margin-bottom:10px;">
          ⚠️ Обнаружены признаки накрученных отзывов${s.fake_reviews_reason ? ": " + s.fake_reviews_reason : ""}
        </div>`;
      }

      if (s.pros?.length) {
        html += `<div class="shopspy-pros"><div class="shopspy-pros-title">👍 Плюсы</div>
          ${s.pros.map((p) => `<div class="shopspy-review-item">${p}</div>`).join("")}</div>`;
      }
      if (s.cons?.length) {
        html += `<div class="shopspy-cons"><div class="shopspy-cons-title">👎 Минусы</div>
          ${s.cons.map((c) => `<div class="shopspy-review-item">${c}</div>`).join("")}</div>`;
      }

      if (s.rating_honest) {
        const stars =
          "★".repeat(Math.round(s.rating_honest)) +
          "☆".repeat(5 - Math.round(s.rating_honest));
        html += `<div style="font-size:13px;color:#ffcc80;margin:8px 0;">
          Честный рейтинг: ${stars} ${s.rating_honest}/5
        </div>`;
      }

      if (s.verdict) {
        html += `<div class="shopspy-ai-verdict">
          <div class="shopspy-ai-badge">AI вердикт</div>
          <div>${s.verdict}</div>
        </div>`;
      }

      const rm = {
        yes: { c: "buy-yes", i: "✅", t: "Можно покупать" },
        no: { c: "buy-no", i: "❌", t: "Лучше не покупать" },
        wait: { c: "buy-wait", i: "⏳", t: "Лучше подождать" },
      };
      const r = rm[s.buy_recommendation];
      if (r) {
        html += `<div class="shopspy-recommendation ${r.c}">
          <span class="shopspy-recommendation-icon">${r.i}</span>
          <span class="shopspy-recommendation-text">${r.t}</span>
        </div>`;
      }

      html += `</div>`;
    } else {
      html += `<div class="shopspy-section">
        <button class="shopspy-btn" id="shopspy-analyze-btn">🤖 Анализировать отзывы (AI)</button>
        <div style="font-size:11px;color:#555;margin-top:6px;text-align:center;">
          Перейдите во вкладку "Отзывы" для лучшего результата
        </div>
      </div>`;
    }

    // ── Подвал ──
    html += `<div class="shopspy-info">
      <span>ShopSpy v0.2</span>
      <span>Данные копятся при просмотре</span>
    </div>`;

    body.innerHTML = html;

    // Обработчик кнопки анализа
    const analyzeBtn = document.getElementById("shopspy-analyze-btn");
    if (analyzeBtn) {
      analyzeBtn.addEventListener("click", async () => {
        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML =
          '<div class="shopspy-spinner" style="display:inline-block;margin-right:8px;"></div> Анализирую...';
        const reviewTexts = data.getReviews();
        if (reviewTexts.length < 2) {
          analyzeBtn.textContent = '⚠️ Мало отзывов. Откройте вкладку "Отзывы"';
          analyzeBtn.disabled = false;
          return;
        }
        const result = await SHOPSPY.analyzeReviews(
          platform,
          productId,
          productName,
          reviewTexts,
        );
        data.reviews = result;
        SHOPSPY.renderPanel(data);
      });
    }

    // Обработчик кнопки отслеживания
    const trackBtn = document.getElementById("shopspy-track-btn");
    const trackStatus = document.getElementById("shopspy-track-status");
    if (trackBtn) {
      trackBtn.addEventListener("click", async () => {
        const wasTracking = SHOPSPY.isTracking;

        // Проверяем авторизацию
        const chatId = await SHOPSPY.getTelegramId();
        if (!chatId) {
          trackStatus.innerHTML =
            '<span style="color:#ef9a9a;">⚠️ Сначала войдите через Telegram (кликните на иконку расширения)</span>';
          return;
        }

        // Показываем процесс
        trackBtn.disabled = true;
        trackBtn.innerHTML =
          '<div class="shopspy-spinner" style="display:inline-block;margin-right:8px;"></div> ' +
          (wasTracking ? "Удаляю..." : "Добавляю...");

        // Отправляем запрос
        const result = await SHOPSPY.toggleTracking(
          platform,
          productId,
          productName,
          window.location.href,
          wasTracking,
        );

        if (result.error) {
          trackStatus.innerHTML =
            '<span style="color:#ef9a9a;">❌ Ошибка. Попробуйте позже</span>';
          trackBtn.disabled = false;
          trackBtn.textContent = wasTracking
            ? "✓ Отслеживается"
            : "🔔 Отслеживать";
        } else {
          SHOPSPY.isTracking = result.tracking;
          if (result.tracking) {
            trackBtn.className = "shopspy-track-btn tracking";
            trackBtn.textContent = "✓ Отслеживается";
            trackStatus.innerHTML =
              '<span style="color:#81c784;">✓ Будем уведомлять о снижении цены в Telegram</span>';
          } else {
            trackBtn.className = "shopspy-track-btn";
            trackBtn.textContent = "🔔 Отслеживать";
            trackStatus.innerHTML =
              '<span style="color:#888;">Отслеживание отключено</span>';
          }
          trackBtn.disabled = false;
        }
      });
    }
  },
};
