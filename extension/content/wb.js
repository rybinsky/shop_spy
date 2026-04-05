/**
 * ShopSpy - Wildberries content script
 */
(function() {
  'use strict';
  const PLATFORM = 'wb';

  function getProductId() {
    const m = window.location.pathname.match(/\/catalog\/(\d+)/);
    return m ? m[1] : null;
  }

  function getProductName() {
    for (const s of ['h1.product-page__title', '.product-page__header h1', '[data-link="text{:product^goodsName}"]', 'h1']) {
      const el = document.querySelector(s);
      if (el && el.textContent.trim().length > 3) return el.textContent.trim();
    }
    return document.title.split(/[-|]/)[0].trim();
  }

  function getCurrentPrice() {
    for (const s of ['.price-block__final-price', 'ins.price-block__final-price', 'span.price-block__final-price', '.price-block__price']) {
      const el = document.querySelector(s);
      if (el) { const v = parseFloat(el.textContent.replace(/[^\d]/g, '')); if (v > 0) return v; }
    }
    return null;
  }

  function getOriginalPrice() {
    for (const s of ['.price-block__old-price del', 'del.price-block__old-price', '.price-block__old-price']) {
      const el = document.querySelector(s);
      if (el) { const v = parseFloat(el.textContent.replace(/[^\d]/g, '')); if (v > 0) return v; }
    }
    return null;
  }

  function getReviews() {
    const r = [];
    document.querySelectorAll('.feedback__text, .comments__item__text, [data-link="text{:comment^text}"]').forEach(el => {
      const t = el.textContent.trim();
      if (t.length > 10) r.push(t);
    });
    return r;
  }

  async function init() {
    const productId = getProductId();
    if (!productId) return;
    SHOPSPY.createPanel();
    const price = getCurrentPrice(), originalPrice = getOriginalPrice(), name = getProductName();
    if (price) await SHOPSPY.sendPrice(PLATFORM, productId, name, price, originalPrice);
    const h = await SHOPSPY.getHistory(PLATFORM, productId);
    SHOPSPY.renderPanel({ history: h.history, analysis: h.analysis, reviews: null, productName: name, price, originalPrice, platform: PLATFORM, productId, getReviews });
  }

  let lastUrl = '';
  setInterval(() => { if (window.location.href !== lastUrl) { lastUrl = window.location.href; if (getProductId()) setTimeout(init, 1500); } }, 1000);
  setTimeout(init, 2000);
})();
