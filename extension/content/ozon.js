/**
 * ShopSpy - Ozon content script
 */
(function() {
  'use strict';
  const PLATFORM = 'ozon';

  function getProductId() {
    const m = window.location.pathname.match(/\/product\/[^/]*-(\d+)\/?/);
    return m ? m[1] : null;
  }

  function getProductName() {
    for (const s of ['[data-widget="webProductHeading"] h1', 'h1.tsHeadline550Medium', 'h1']) {
      const el = document.querySelector(s);
      if (el && el.textContent.trim().length > 3) return el.textContent.trim();
    }
    return document.title.split(/[-|]/)[0].trim();
  }

  function getCurrentPrice() {
    console.log('ShopSpy Ozon: getCurrentPrice called');
    
    // Сначала пробуем цену с Ozon Банком (выгоднее)
    const bankPrice = document.querySelector('.tsHeadline600Large');
    if (bankPrice) {
      const v = parseFloat(bankPrice.textContent.replace(/[^\d]/g, ''));
      console.log('ShopSpy Ozon: bankPrice =', v);
      if (v > 0) return v;
    }
    
    // Потом цена без банка
    const regularPrice = document.querySelector('.pdp_jb.tsHeadline500Medium, .tsHeadline500Medium');
    if (regularPrice) {
      const v = parseFloat(regularPrice.textContent.replace(/[^\d]/g, ''));
      console.log('ShopSpy Ozon: regularPrice =', v);
      if (v > 0) return v;
    }
    
    // Fallback - старые селекторы
    for (const s of ['[data-widget="webPrice"] span:first-child', 'span.tsHeadline500Medium', 'div[data-widget="webPrice"] span']) {
      const el = document.querySelector(s);
      if (el) { const v = parseFloat(el.textContent.replace(/[^\d]/g, '')); if (v > 0) return v; }
    }
    return null;
  }
  
  function getOriginalPrice() {
    console.log('ShopSpy Ozon: getOriginalPrice called');
    
    // Старая зачёркнутая цена
    const oldPrice = document.querySelector('.pdp_bj.pdp_b0j.pdp_b9i, .pdp_b9i');
    if (oldPrice) {
      const v = parseFloat(oldPrice.textContent.replace(/[^\d]/g, ''));
      console.log('ShopSpy Ozon: oldPrice =', v);
      if (v > 0) return v;
    }
    
    // Fallback - старые селекторы
    for (const s of ['[data-widget="webPrice"] span[style*="line-through"]', 'span[style*="line-through"]']) {
      const el = document.querySelector(s);
      if (el) { const v = parseFloat(el.textContent.replace(/[^\d]/g, '')); if (v > 0) return v; }
    }
    return null;
  }

  function getReviews() {
    const r = [];
    document.querySelectorAll('[data-widget="webReviewComments"] div[itemprop="description"], [data-review-text], .review-text').forEach(el => {
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
