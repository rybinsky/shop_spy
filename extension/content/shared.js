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

  async getHistory(platform, productId) {
    try {
      const r = await fetch(
        `${this.API_BASE}/api/price/history?platform=${platform}&product_id=${productId}`,
      );
      return await r.json();
    } catch (e) {
      return {
        history: [],
        analysis: {
          verdict: "error",
          message: "Сервер недоступен. Попробуйте позже.",
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
      return await r.json();
    } catch (e) {
      return {
        summary: {
          pros: [],
          cons: [],
          verdict: "Сервер недоступен",
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

    // ── Блок: Текущие цены ──
    if (price || cardPrice) {
      // Рассчитываем скидки
      const discountFromOriginal =
        originalPrice && originalPrice > price
          ? Math.round((1 - price / originalPrice) * 100)
          : null;
      const cardDiscount =
        originalPrice && cardPrice
          ? Math.round((1 - cardPrice / originalPrice) * 100)
          : null;
      const cardVsRegular =
        price && cardPrice && cardPrice < price
          ? Math.round((1 - cardPrice / price) * 100)
          : null;

      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">💰 Текущие цены</div>`;

      // Цена по карте (если есть)
      if (cardPrice && cardPrice !== price) {
        html += `<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">
          <span style="font-size:11px;${cardBadgeBg};-webkit-background-clip:text;-webkit-text-fill-color:transparent;padding:2px 6px;border-radius:4px;font-weight:600;">${cardName}</span>
          <span style="font-size:24px;font-weight:700;color:${cardPriceColor};">${cardPrice.toLocaleString("ru")} ₽</span>`;
        if (cardDiscount) {
          html += `<span style="font-size:12px;font-weight:600;color:#4ade80;">−${cardDiscount}%</span>`;
        }
        html += `</div>`;
      }

      // Основная цена (без карты)
      if (price) {
        html += `<div style="display:flex;align-items:baseline;gap:10px;">
          <span style="font-size:20px;font-weight:700;color:#fff;">${price.toLocaleString("ru")} ₽</span>`;
        if (originalPrice && originalPrice > price) {
          html += `<span style="font-size:13px;text-decoration:line-through;color:#666;">${originalPrice.toLocaleString("ru")} ₽</span>
            <span style="font-size:12px;font-weight:600;color:#e94560;">−${discountFromOriginal}%</span>`;
        }
        html += `</div>`;
      }

      // Экономия с картой
      if (cardVsRegular) {
        html += `<div style="margin-top:8px;padding:8px 10px;background:${cardBadgeBgRgba};border:1px solid ${cardBadgeBorderRgba};border-radius:6px;">
          <span style="font-size:12px;color:${cardBadgeTextRgba};">${cardEmoji} С ${cardName.replace("Кошелёк", "кошельком").replace("Банк", "картой")} экономия ${cardVsRegular}%</span>
        </div>`;
      }

      html += `</div>`;
    }

    // ── Блок: Анализ цены ──
    html += `<div class="shopspy-section">
      <div class="shopspy-section-title">📊 Анализ цены</div>
      <div class="shopspy-verdict ${analysis.verdict}">
        <span class="shopspy-verdict-icon">${icons[analysis.verdict] || "ℹ️"}</span>
        ${analysis.message}
      </div>
    </div>`;

    // ── Блок: График цен ──
    if (history && history.length > 1) {
      const prices = history.map((h) => h.price);
      const cardPrices = history
        .map((h) => h.card_price)
        .filter((p) => p !== null && p !== undefined);

      // Находим min/max включая обе цены
      const allValues = [...prices, ...cardPrices];
      let min = Math.min(...allValues);
      let max = Math.max(...allValues);
      const range = max - min || 1;
      const W = 340,
        H = 80;

      // Точки для основной цены
      const pts = prices
        .map(
          (p, i) =>
            `${(i / (prices.length - 1)) * W},${H - ((p - min) / range) * (H - 10) - 5}`,
        )
        .join(" ");

      // Точки для цены по карте (фиолетовая линия)
      let cardPts = "";
      if (cardPrices.length > 0) {
        const cardHistory = history.filter(
          (h) => h.card_price !== null && h.card_price !== undefined,
        );
        cardPts = cardHistory
          .map(
            (h, i) =>
              `${(i / (cardHistory.length - 1)) * W},${H - ((h.card_price - min) / range) * (H - 10) - 5}`,
          )
          .join(" ");
      }

      const avgPrice =
        analysis.avg_price ||
        Math.round(prices.reduce((a, b) => a + b, 0) / prices.length);

      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">📈 История цен (${history.length} точек)</div>
        <svg width="${W}" height="${H}" style="width:100%;background:rgba(255,255,255,0.03);border-radius:8px;">
          <defs>
            <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#e94560" stop-opacity="0.3"/>
              <stop offset="100%" stop-color="#e94560" stop-opacity="0"/>
            </linearGradient>
            <linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="${cardPriceColor}" stop-opacity="0.3"/>
              <stop offset="100%" stop-color="${cardPriceColor}" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <polygon points="0,${H} ${pts} ${W},${H}" fill="url(#sg)"/>
          <polyline points="${pts}" fill="none" stroke="#e94560" stroke-width="2"/>
          ${cardPts ? `<polyline points="${cardPts}" fill="none" stroke="${cardPriceColor}" stroke-width="2" stroke-dasharray="4,2"/>` : ""}
          <!-- Линия средней цены -->
          <line x1="0" y1="${H - ((avgPrice - min) / range) * (H - 10) - 5}"
                x2="${W}" y2="${H - ((avgPrice - min) / range) * (H - 10) - 5}"
                stroke="#888" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>
        </svg>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:#666;margin-top:4px;">
          <span>мин: ${min.toLocaleString("ru")} ₽</span>
          <span style="color:#888;">сред: ${avgPrice.toLocaleString("ru")} ₽</span>
          <span>макс: ${max.toLocaleString("ru")} ₽</span>
        </div>
        ${
          cardPrices.length > 0
            ? `<div style="display:flex;gap:16px;font-size:11px;margin-top:6px;">
          <span style="display:flex;align-items:center;gap:4px;"><span style="width:12px;height:2px;background:#e94560;border-radius:1px;"></span>Обычная</span>
          <span style="display:flex;align-items:center;gap:4px;"><span style="width:12px;height:2px;background:${cardPriceColor};border-radius:1px;border-top:1px dashed ${cardPriceColor};"></span>${cardName}</span>
        </div>`
            : ""
        }
      </div>`;

      // ── Блок: Экономия ──
      if (price && price < avgPrice) {
        const savings = Math.round(avgPrice - price);
        html += `<div class="shopspy-section">
          <div style="padding:10px 12px;background:rgba(76,175,80,0.12);border:1px solid rgba(76,175,80,0.25);border-radius:8px;display:flex;align-items:center;gap:10px;">
            <span style="font-size:20px;">💸</span>
            <span style="font-size:13px;color:#81c784;">Вы экономите ~${savings.toLocaleString("ru")} ₽ по сравнению со средней ценой</span>
          </div>
        </div>`;
      }
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
