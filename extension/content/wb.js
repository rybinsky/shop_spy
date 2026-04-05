/**
 * ShopSpy - Content script для Wildberries
 * Собирает цены, отзывы, показывает AI-анализ
 */

(function() {
  'use strict';

  // ── НАСТРОЙКА: замените на URL вашего сервера на Render ──
  // Для локальной работы: 'http://localhost:8000'
  // Для Render: 'https://shopspy-xxxx.onrender.com'
  const API_BASE = 'http://localhost:8000';
  const PLATFORM = 'wb';

  let panelCreated = false;
  let currentProductId = null;

  // ── Извлечение данных со страницы WB ──

  function getProductId() {
    const match = window.location.pathname.match(/\/catalog\/(\d+)/);
    return match ? match[1] : null;
  }

  function getProductName() {
    const el = document.querySelector('.product-page__header h1, [data-link="text{:product^goodsName}"], .product-page__title');
    return el ? el.textContent.trim() : document.title.split('купить')[0].trim();
  }

  function getCurrentPrice() {
    // WB часто меняет верстку, пробуем несколько селекторов
    const selectors = [
      '.price-block__final-price',
      '.price-block__price',
      '[data-link="text{:product^priceForProduct}"]',
      '.product-page__price-block .price-block__final-price',
      'ins.price-block__final-price',
      'span.price-block__final-price'
    ];

    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) {
        const text = el.textContent.replace(/[^\d.,]/g, '').replace(',', '.');
        const price = parseFloat(text);
        if (price > 0) return price;
      }
    }

    return null;
  }

  function getOriginalPrice() {
    const selectors = [
      '.price-block__old-price del',
      '.price-block__old-price',
      'del.price-block__old-price'
    ];

    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) {
        const text = el.textContent.replace(/[^\d.,]/g, '').replace(',', '.');
        const price = parseFloat(text);
        if (price > 0) return price;
      }
    }
    return null;
  }

  function getReviews() {
    const reviewEls = document.querySelectorAll('.feedback__text, .comments__item__text, [data-link="text{:comment^text}"]');
    const reviews = [];
    reviewEls.forEach(el => {
      const text = el.textContent.trim();
      if (text.length > 10) reviews.push(text);
    });
    return reviews;
  }

  // ── API вызовы ──

  async function sendPrice(productId, name, price, originalPrice) {
    try {
      await fetch(`${API_BASE}/api/price`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: PLATFORM,
          product_id: productId,
          product_name: name,
          price: price,
          original_price: originalPrice,
          url: window.location.href
        })
      });
    } catch (e) {
      console.log('ShopSpy: бэкенд недоступен', e.message);
    }
  }

  async function getHistory(productId) {
    try {
      const resp = await fetch(`${API_BASE}/api/price/history?platform=${PLATFORM}&product_id=${productId}`);
      return await resp.json();
    } catch (e) {
      return { history: [], analysis: { verdict: 'error', message: 'Бэкенд недоступен. Запустите: python backend/main.py' } };
    }
  }

  async function analyzeReviews(productId, name, reviews) {
    try {
      const resp = await fetch(`${API_BASE}/api/reviews/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: PLATFORM,
          product_id: productId,
          product_name: name,
          reviews: reviews
        })
      });
      return await resp.json();
    } catch (e) {
      return { summary: { pros: [], cons: [], verdict: 'Бэкенд недоступен', buy_recommendation: 'unknown' } };
    }
  }

  // ── UI ──

  function createPanel() {
    if (panelCreated) return document.getElementById('shopspy-panel');

    const panel = document.createElement('div');
    panel.id = 'shopspy-panel';
    panel.className = 'shopspy-panel';
    panel.innerHTML = `
      <div class="shopspy-header" id="shopspy-toggle">
        <div class="shopspy-logo">
          <span class="shopspy-logo-icon">🔍</span>
          <span>ShopSpy</span>
        </div>
        <button class="shopspy-close" id="shopspy-collapse">−</button>
      </div>
      <div class="shopspy-body" id="shopspy-body">
        <div class="shopspy-loader">
          <div class="shopspy-spinner"></div>
          Анализирую товар...
        </div>
      </div>
    `;

    document.body.appendChild(panel);
    panelCreated = true;

    document.getElementById('shopspy-collapse').addEventListener('click', (e) => {
      e.stopPropagation();
      panel.classList.toggle('collapsed');
    });

    document.getElementById('shopspy-toggle').addEventListener('click', () => {
      if (panel.classList.contains('collapsed')) {
        panel.classList.remove('collapsed');
      }
    });

    return panel;
  }

  function renderPanel(data) {
    const body = document.getElementById('shopspy-body');
    if (!body) return;

    const { history, analysis, reviews: reviewData } = data;
    const verdictIcons = {
      good_deal: '✅',
      fake_discount: '🚨',
      overpriced: '⚠️',
      normal: 'ℹ️',
      insufficient_data: '📊',
      error: '❌'
    };

    let html = '';

    // Секция: анализ цены
    html += `
      <div class="shopspy-section">
        <div class="shopspy-section-title">Анализ цены</div>
        <div class="shopspy-verdict ${analysis.verdict}">
          <span class="shopspy-verdict-icon">${verdictIcons[analysis.verdict] || 'ℹ️'}</span>
          ${analysis.message}
        </div>
      </div>
    `;

    // Секция: мини-график если есть история
    if (history && history.length > 1) {
      const prices = history.map(h => h.price);
      const min = Math.min(...prices);
      const max = Math.max(...prices);
      const range = max - min || 1;

      const svgWidth = 340;
      const svgHeight = 80;
      const points = prices.map((p, i) => {
        const x = (i / (prices.length - 1)) * svgWidth;
        const y = svgHeight - ((p - min) / range) * (svgHeight - 10) - 5;
        return `${x},${y}`;
      }).join(' ');

      html += `
        <div class="shopspy-section">
          <div class="shopspy-section-title">История цен (${history.length} записей)</div>
          <svg width="${svgWidth}" height="${svgHeight}" style="width:100%;background:rgba(255,255,255,0.03);border-radius:8px;">
            <defs>
              <linearGradient id="shopspy-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#e94560" stop-opacity="0.3"/>
                <stop offset="100%" stop-color="#e94560" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <polygon points="0,${svgHeight} ${points} ${svgWidth},${svgHeight}" fill="url(#shopspy-grad)"/>
            <polyline points="${points}" fill="none" stroke="#e94560" stroke-width="2"/>
          </svg>
          <div style="display:flex;justify-content:space-between;font-size:11px;color:#666;margin-top:4px;">
            <span>мин: ${min.toLocaleString('ru')} ₽</span>
            <span>макс: ${max.toLocaleString('ru')} ₽</span>
          </div>
        </div>
      `;
    }

    // Секция: AI-анализ отзывов
    if (reviewData) {
      const s = reviewData.summary || reviewData;
      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">AI-анализ отзывов</div>`;

      if (s.pros && s.pros.length) {
        html += `<div class="shopspy-pros">
          <div class="shopspy-pros-title">👍 Плюсы</div>
          ${s.pros.map(p => `<div class="shopspy-review-item">${p}</div>`).join('')}
        </div>`;
      }

      if (s.cons && s.cons.length) {
        html += `<div class="shopspy-cons">
          <div class="shopspy-cons-title">👎 Минусы</div>
          ${s.cons.map(c => `<div class="shopspy-review-item">${c}</div>`).join('')}
        </div>`;
      }

      if (s.verdict) {
        html += `<div class="shopspy-ai-verdict">
          <div class="shopspy-ai-badge">AI вердикт</div>
          <div>${s.verdict}</div>
        </div>`;
      }

      const recMap = {
        yes: { cls: 'buy-yes', icon: '✅', text: 'Можно покупать' },
        no: { cls: 'buy-no', icon: '❌', text: 'Лучше не покупать' },
        wait: { cls: 'buy-wait', icon: '⏳', text: 'Лучше подождать' },
      };
      const rec = recMap[s.buy_recommendation];
      if (rec) {
        html += `<div class="shopspy-recommendation ${rec.cls}">
          <span class="shopspy-recommendation-icon">${rec.icon}</span>
          <span class="shopspy-recommendation-text">${rec.text}</span>
        </div>`;
      }

      html += `</div>`;
    } else {
      html += `
        <div class="shopspy-section">
          <button class="shopspy-btn" id="shopspy-analyze-btn">
            🤖 Анализировать отзывы (AI)
          </button>
        </div>
      `;
    }

    // Инфо
    html += `<div class="shopspy-info">
      <span>ShopSpy v0.1</span>
      <span>localhost:8000</span>
    </div>`;

    body.innerHTML = html;

    // Привязка кнопки анализа отзывов
    const analyzeBtn = document.getElementById('shopspy-analyze-btn');
    if (analyzeBtn) {
      analyzeBtn.addEventListener('click', async () => {
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = '⏳ Анализирую...';
        const reviews = getReviews();
        if (reviews.length < 2) {
          analyzeBtn.textContent = 'Мало отзывов на странице. Откройте вкладку отзывов.';
          return;
        }
        const result = await analyzeReviews(currentProductId, getProductName(), reviews);
        renderPanel({ history, analysis, reviews: result });
      });
    }
  }

  // ── Main ──

  async function init() {
    const productId = getProductId();
    if (!productId) return;

    currentProductId = productId;
    createPanel();

    const price = getCurrentPrice();
    const originalPrice = getOriginalPrice();
    const name = getProductName();

    if (price) {
      await sendPrice(productId, name, price, originalPrice);
    }

    const historyData = await getHistory(productId);
    renderPanel({
      history: historyData.history,
      analysis: historyData.analysis,
      reviews: null
    });
  }

  // Ждем загрузки страницы и повторяем при навигации (SPA)
  let lastUrl = '';
  function checkUrl() {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      if (getProductId()) {
        setTimeout(init, 1500); // ждем загрузки контента WB
      }
    }
  }

  setInterval(checkUrl, 1000);
  setTimeout(init, 2000);

})();
