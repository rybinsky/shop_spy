/**
 * ShopSpy - Content script для Ozon
 */

(function() {
  'use strict';

  // ── НАСТРОЙКА: замените на URL вашего сервера на Render ──
  const API_BASE = 'http://localhost:8000';
  const PLATFORM = 'ozon';

  let panelCreated = false;
  let currentProductId = null;

  function getProductId() {
    const match = window.location.pathname.match(/\/product\/[^/]*-(\d+)\/?/);
    return match ? match[1] : null;
  }

  function getProductName() {
    const el = document.querySelector('[data-widget="webProductHeading"] h1, h1.tsHeadline550Medium');
    return el ? el.textContent.trim() : document.title.split('купить')[0].trim();
  }

  function getCurrentPrice() {
    const selectors = [
      '[data-widget="webPrice"] span:first-child',
      'span.tsHeadline500Medium',
      'div[data-widget="webPrice"] span'
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
      '[data-widget="webPrice"] span[style*="line-through"]',
      'span.tsBodyControl400Small[style*="line-through"]'
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
    const reviewEls = document.querySelectorAll('[data-widget="webReviewComments"] div[itemprop="description"], [data-review-text], .review-text');
    const reviews = [];
    reviewEls.forEach(el => {
      const text = el.textContent.trim();
      if (text.length > 10) reviews.push(text);
    });
    return reviews;
  }

  // Переиспользуем те же функции API и UI что в wb.js
  // (в продакшене вынести в shared модуль)

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
        body: JSON.stringify({ platform: PLATFORM, product_id: productId, product_name: name, reviews })
      });
      return await resp.json();
    } catch (e) {
      return { summary: { pros: [], cons: [], verdict: 'Бэкенд недоступен', buy_recommendation: 'unknown' } };
    }
  }

  function createPanel() {
    if (panelCreated) return;
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
        <div class="shopspy-loader"><div class="shopspy-spinner"></div> Анализирую товар...</div>
      </div>
    `;
    document.body.appendChild(panel);
    panelCreated = true;

    document.getElementById('shopspy-collapse').addEventListener('click', (e) => {
      e.stopPropagation();
      panel.classList.toggle('collapsed');
    });
    document.getElementById('shopspy-toggle').addEventListener('click', () => {
      if (panel.classList.contains('collapsed')) panel.classList.remove('collapsed');
    });
  }

  function renderPanel(data) {
    const body = document.getElementById('shopspy-body');
    if (!body) return;

    const { history, analysis, reviews: reviewData } = data;
    const icons = { good_deal:'✅', fake_discount:'🚨', overpriced:'⚠️', normal:'ℹ️', insufficient_data:'📊', error:'❌' };

    let html = `
      <div class="shopspy-section">
        <div class="shopspy-section-title">Анализ цены</div>
        <div class="shopspy-verdict ${analysis.verdict}">
          <span class="shopspy-verdict-icon">${icons[analysis.verdict]||'ℹ️'}</span>
          ${analysis.message}
        </div>
      </div>`;

    if (history && history.length > 1) {
      const prices = history.map(h => h.price);
      const min = Math.min(...prices), max = Math.max(...prices), range = max-min||1;
      const W=340, H=80;
      const pts = prices.map((p,i) => `${(i/(prices.length-1))*W},${H-((p-min)/range)*(H-10)-5}`).join(' ');

      html += `<div class="shopspy-section">
        <div class="shopspy-section-title">История цен (${history.length} записей)</div>
        <svg width="${W}" height="${H}" style="width:100%;background:rgba(255,255,255,0.03);border-radius:8px;">
          <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#e94560" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#e94560" stop-opacity="0"/>
          </linearGradient></defs>
          <polygon points="0,${H} ${pts} ${W},${H}" fill="url(#sg)"/>
          <polyline points="${pts}" fill="none" stroke="#e94560" stroke-width="2"/>
        </svg>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:#666;margin-top:4px;">
          <span>мин: ${min.toLocaleString('ru')} ₽</span>
          <span>макс: ${max.toLocaleString('ru')} ₽</span>
        </div>
      </div>`;
    }

    if (reviewData) {
      const s = reviewData.summary || reviewData;
      html += `<div class="shopspy-section"><div class="shopspy-section-title">AI-анализ отзывов</div>`;
      if (s.pros?.length) html += `<div class="shopspy-pros"><div class="shopspy-pros-title">👍 Плюсы</div>${s.pros.map(p=>`<div class="shopspy-review-item">${p}</div>`).join('')}</div>`;
      if (s.cons?.length) html += `<div class="shopspy-cons"><div class="shopspy-cons-title">👎 Минусы</div>${s.cons.map(c=>`<div class="shopspy-review-item">${c}</div>`).join('')}</div>`;
      if (s.verdict) html += `<div class="shopspy-ai-verdict"><div class="shopspy-ai-badge">AI вердикт</div><div>${s.verdict}</div></div>`;
      const rm = {yes:{c:'buy-yes',i:'✅',t:'Можно покупать'},no:{c:'buy-no',i:'❌',t:'Лучше не покупать'},wait:{c:'buy-wait',i:'⏳',t:'Лучше подождать'}};
      const r = rm[s.buy_recommendation];
      if (r) html += `<div class="shopspy-recommendation ${r.c}"><span class="shopspy-recommendation-icon">${r.i}</span><span class="shopspy-recommendation-text">${r.t}</span></div>`;
      html += `</div>`;
    } else {
      html += `<div class="shopspy-section"><button class="shopspy-btn" id="shopspy-analyze-btn">🤖 Анализировать отзывы (AI)</button></div>`;
    }

    html += `<div class="shopspy-info"><span>ShopSpy v0.1</span><span>localhost:8000</span></div>`;
    body.innerHTML = html;

    const btn = document.getElementById('shopspy-analyze-btn');
    if (btn) {
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.textContent = '⏳ Анализирую...';
        const reviews = getReviews();
        if (reviews.length < 2) { btn.textContent = 'Мало отзывов. Откройте вкладку отзывов.'; return; }
        const result = await analyzeReviews(currentProductId, getProductName(), reviews);
        renderPanel({ history, analysis, reviews: result });
      });
    }
  }

  async function init() {
    const productId = getProductId();
    if (!productId) return;
    currentProductId = productId;
    createPanel();

    const price = getCurrentPrice();
    const originalPrice = getOriginalPrice();
    const name = getProductName();
    if (price) await sendPrice(productId, name, price, originalPrice);

    const historyData = await getHistory(productId);
    renderPanel({ history: historyData.history, analysis: historyData.analysis, reviews: null });
  }

  let lastUrl = '';
  function checkUrl() {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      if (getProductId()) setTimeout(init, 1500);
    }
  }
  setInterval(checkUrl, 1000);
  setTimeout(init, 2000);

})();
