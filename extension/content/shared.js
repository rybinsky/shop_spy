/**
 * ShopSpy - Общий модуль для content-скриптов
 * Единый UI, API-вызовы, логика для WB и Ozon
 */

const SHOPSPY = {
  API_BASE: 'https://shop-spy.onrender.com',
  panelCreated: false,
  currentProductId: null,
  currentPlatform: null,
  historyData: null,
  analysisData: null,

  // ── API ──

  async sendPrice(platform, productId, name, price, originalPrice) {
    try {
      await fetch(`${this.API_BASE}/api/price`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform, product_id: productId, product_name: name,
          price, original_price: originalPrice,
          url: window.location.href
        })
      });
    } catch (e) {
      console.log('ShopSpy: сервер недоступен', e.message);
    }
  },

  async getHistory(platform, productId) {
    try {
      const r = await fetch(`${this.API_BASE}/api/price/history?platform=${platform}&product_id=${productId}`);
      return await r.json();
    } catch (e) {
      return { history: [], analysis: { verdict: 'error', message: 'Сервер недоступен. Попробуйте позже.' } };
    }
  },

  async analyzeReviews(platform, productId, name, reviews) {
    try {
      const r = await fetch(`${this.API_BASE}/api/reviews/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, product_id: productId, product_name: name, reviews })
      });
      return await r.json();
    } catch (e) {
      return { summary: { pros: [], cons: [], verdict: 'Сервер недоступен', buy_recommendation: 'unknown' } };
    }
  },

  // ── UI: Создание панели ──

  createPanel() {
    if (this.panelCreated) return;

    const panel = document.createElement('div');
    panel.id = 'shopspy-panel';
    panel.className = 'shopspy-panel';
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

    document.getElementById('shopspy-collapse').addEventListener('click', (e) => {
      e.stopPropagation();
      panel.classList.toggle('collapsed');
    });
    document.getElementById('shopspy-toggle').addEventListener('click', () => {
      if (panel.classList.contains('collapsed')) panel.classList.remove('collapsed');
    });
  },

  // ── UI: Рендер контента ──

  renderPanel(data) {
    const body = document.getElementById('shopspy-body');
    if (!body) return;

    const { history, analysis, reviews, productName, price, originalPrice, platform, productId } = data;
    const icons = {
      good_deal: '✅', fake_discount: '🚨', overpriced: '⚠️',
      normal: 'ℹ️', insufficient_data: '📊', error: '❌'
    };

    let html = '';

    // ── Блок: Текущая цена ──
    if (price) {
      const discount = originalPrice && originalPrice > price
        ? Math.round((1 - price / originalPrice) * 100)
        : null;

      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">💰 Текущая цена</div>
        <div style="display:flex;align-items:baseline;gap:10px;">
          <span style="font-size:22px;font-weight:700;color:#fff;">${price.toLocaleString('ru')} ₽</span>`;

      if (originalPrice && originalPrice > price) {
        html += `<span style="font-size:14px;text-decoration:line-through;color:#666;">${originalPrice.toLocaleString('ru')} ₽</span>
          <span style="font-size:13px;font-weight:600;color:#e94560;">−${discount}%</span>`;
      }
      html += `</div></div>`;
    }

    // ── Блок: Анализ цены ──
    html += `<div class="shopspy-section">
      <div class="shopspy-section-title">📊 Анализ цены</div>
      <div class="shopspy-verdict ${analysis.verdict}">
        <span class="shopspy-verdict-icon">${icons[analysis.verdict] || 'ℹ️'}</span>
        ${analysis.message}
      </div>
    </div>`;

    // ── Блок: График цен ──
    if (history && history.length > 1) {
      const prices = history.map(h => h.price);
      const min = Math.min(...prices), max = Math.max(...prices), range = max - min || 1;
      const W = 340, H = 80;
      const pts = prices.map((p, i) =>
        `${(i / (prices.length - 1)) * W},${H - ((p - min) / range) * (H - 10) - 5}`
      ).join(' ');

      // Находим лучшую и худшую цену
      const bestPrice = min;
      const avgPrice = analysis.avg_price || Math.round(prices.reduce((a, b) => a + b, 0) / prices.length);

      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">📈 История цен (${history.length} точек)</div>
        <svg width="${W}" height="${H}" style="width:100%;background:rgba(255,255,255,0.03);border-radius:8px;">
          <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#e94560" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#e94560" stop-opacity="0"/>
          </linearGradient></defs>
          <polygon points="0,${H} ${pts} ${W},${H}" fill="url(#sg)"/>
          <polyline points="${pts}" fill="none" stroke="#e94560" stroke-width="2"/>
          <!-- Линия средней цены -->
          <line x1="0" y1="${H - ((avgPrice - min) / range) * (H - 10) - 5}"
                x2="${W}" y2="${H - ((avgPrice - min) / range) * (H - 10) - 5}"
                stroke="#888" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>
        </svg>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:#666;margin-top:4px;">
          <span>мин: ${min.toLocaleString('ru')} ₽</span>
          <span style="color:#888;">сред: ${avgPrice.toLocaleString('ru')} ₽</span>
          <span>макс: ${max.toLocaleString('ru')} ₽</span>
        </div>
      </div>`;

      // ── Блок: Экономия ──
      if (price && price < avgPrice) {
        const savings = Math.round(avgPrice - price);
        html += `<div class="shopspy-section">
          <div style="padding:10px 12px;background:rgba(76,175,80,0.12);border:1px solid rgba(76,175,80,0.25);border-radius:8px;display:flex;align-items:center;gap:10px;">
            <span style="font-size:20px;">💸</span>
            <span style="font-size:13px;color:#81c784;">Вы экономите ~${savings.toLocaleString('ru')} ₽ по сравнению со средней ценой</span>
          </div>
        </div>`;
      }
    }

    // ── Блок: Сравнение площадок ──
    const otherPlatform = platform === 'wb' ? 'ozon' : 'wb';
    const otherName = platform === 'wb' ? 'Ozon' : 'Wildberries';
    const searchUrl = platform === 'wb'
      ? `https://www.ozon.ru/search/?text=${encodeURIComponent(productName || '')}`
      : `https://www.wildberries.ru/catalog/0/search.aspx?search=${encodeURIComponent(productName || '')}`;

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
          ⚠️ Обнаружены признаки накрученных отзывов${s.fake_reviews_reason ? ': ' + s.fake_reviews_reason : ''}
        </div>`;
      }

      if (s.pros?.length) {
        html += `<div class="shopspy-pros"><div class="shopspy-pros-title">👍 Плюсы</div>
          ${s.pros.map(p => `<div class="shopspy-review-item">${p}</div>`).join('')}</div>`;
      }
      if (s.cons?.length) {
        html += `<div class="shopspy-cons"><div class="shopspy-cons-title">👎 Минусы</div>
          ${s.cons.map(c => `<div class="shopspy-review-item">${c}</div>`).join('')}</div>`;
      }

      if (s.rating_honest) {
        const stars = '★'.repeat(Math.round(s.rating_honest)) + '☆'.repeat(5 - Math.round(s.rating_honest));
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
        yes: { c: 'buy-yes', i: '✅', t: 'Можно покупать' },
        no: { c: 'buy-no', i: '❌', t: 'Лучше не покупать' },
        wait: { c: 'buy-wait', i: '⏳', t: 'Лучше подождать' }
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
    const btn = document.getElementById('shopspy-analyze-btn');
    if (btn) {
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.innerHTML = '<div class="shopspy-spinner" style="display:inline-block;margin-right:8px;"></div> Анализирую...';
        const reviewTexts = data.getReviews();
        if (reviewTexts.length < 2) {
          btn.textContent = '⚠️ Мало отзывов. Откройте вкладку "Отзывы"';
          btn.disabled = false;
          return;
        }
        const result = await SHOPSPY.analyzeReviews(platform, productId, productName, reviewTexts);
        data.reviews = result;
        SHOPSPY.renderPanel(data);
      });
    }
  }
};
