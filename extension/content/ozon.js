/**
 * ShopSpy - Ozon content script
 *
 * Берём цену БЕЗ Ozon Банка (вторая строка в блоке цен).
 */
(function () {
  "use strict";
  const PLATFORM = "ozon";

  /**
   * Извлекает первое число перед ₽ из строки.
   * "26 990 ₽" → 26990,  "25 910 ₽2 699 ₽" → 25910 (первое)
   */
  function parseFirstPrice(text) {
    if (!text) return null;
    const m = text.match(/(\d[\d\s\u00a0\u2009]*)\s*₽/);
    if (!m) return null;
    const v = parseFloat(m[1].replace(/[\s\u00a0\u2009]/g, ""));
    return v > 0 ? v : null;
  }

  function getProductId() {
    const m = window.location.pathname.match(/\/product\/[^/]*-(\d+)\/?/);
    return m ? m[1] : null;
  }

  function getProductName() {
    for (const s of [
      '[data-widget="webProductHeading"] h1',
      "h1.tsHeadline550Medium",
      "h1",
    ]) {
      const el = document.querySelector(s);
      if (el && el.textContent.trim().length > 3) return el.textContent.trim();
    }
    return document.title.split(/[-|]/)[0].trim();
  }

  function getCurrentPrice() {
    console.log("ShopSpy Ozon: getCurrentPrice called");

    const webPrice = document.querySelector('[data-widget="webPrice"]');
    if (!webPrice) return null;

    // Ищем строку "без Ozon Банка" и берём цену из того же контейнера
    const allSpans = webPrice.querySelectorAll("span");
    for (const span of allSpans) {
      if (span.textContent.includes("без") && span.textContent.includes("Банка")) {
        // Цена — в родительском блоке этого span, ищем ближайшее число с ₽
        const parent = span.closest("div") || span.parentElement;
        if (parent) {
          const v = parseFirstPrice(parent.textContent);
          console.log("ShopSpy Ozon: price near 'без Банка' =", v);
          if (v) return v;
        }
      }
    }

    // Fallback — все цены из webPrice, берём вторую (первая = с банком)
    const allPrices = [];
    for (const raw of webPrice.textContent.matchAll(/(\d[\d\s\u00a0\u2009]*)\s*₽/g)) {
      const clean = raw[1].replace(/[\s\u00a0\u2009]/g, "");
      const v = parseFloat(clean);
      if (v > 0 && v < 100_000_000) allPrices.push(v);
    }
    console.log("ShopSpy Ozon: all prices in widget =", allPrices);

    // Если есть 2+ цен — вторая это "без банка", если одна — берём её
    if (allPrices.length >= 2) return allPrices[1];
    if (allPrices.length === 1) return allPrices[0];

    return null;
  }

  function getOriginalPrice() {
    console.log("ShopSpy Ozon: getOriginalPrice called");

    // Зачёркнутая цена (line-through)
    for (const s of [
      '[data-widget="webPrice"] span[style*="line-through"]',
      'span[style*="line-through"]',
    ]) {
      const el = document.querySelector(s);
      if (el) {
        const v = parseFirstPrice(el.textContent);
        console.log("ShopSpy Ozon: oldPrice =", v);
        if (v) return v;
      }
    }

    // Fallback — класс зачёркнутой цены
    const oldEl = document.querySelector(".pdp_bj.pdp_b0j.pdp_b9i, .pdp_b9i");
    if (oldEl) {
      const v = parseFirstPrice(oldEl.textContent);
      if (v) return v;
    }

    return null;
  }

  function getReviews() {
    const r = [];
    document.querySelectorAll("[data-review-uuid]").forEach((reviewEl) => {
      const spans = reviewEl.querySelectorAll("span");
      let longest = "";
      spans.forEach((sp) => {
        const t = sp.textContent.trim();
        if (
          t.length > longest.length &&
          t.length > 5 &&
          !t.match(/^\d+ \w+ \d{4}$/) &&
          !t.match(/^(Да|Нет) \d+$/) &&
          !t.match(/^(Длина|Цвет|Размер|Название)/) &&
          !t.includes("Вам помог")
        ) {
          longest = t;
        }
      });
      if (longest.length > 5) r.push(longest);
    });

    if (r.length === 0) {
      document
        .querySelectorAll(
          '[data-widget="webReviewComments"] div[itemprop="description"], [data-widget="webListReviews"] span',
        )
        .forEach((el) => {
          const t = el.textContent.trim();
          if (t.length > 15 && !r.includes(t)) r.push(t);
        });
    }
    return r;
  }

  async function init() {
    console.log("ShopSpy Ozon: init started");

    const productId = getProductId();
    console.log("ShopSpy Ozon: productId =", productId);

    if (!productId) {
      console.log("ShopSpy Ozon: no productId, exit");
      return;
    }

    SHOPSPY.createPanel();

    const price = getCurrentPrice();
    const originalPrice = getOriginalPrice();
    const name = getProductName();

    console.log("ShopSpy Ozon: price =", price);
    console.log("ShopSpy Ozon: originalPrice =", originalPrice);
    console.log("ShopSpy Ozon: name =", name);

    if (price) {
      console.log("ShopSpy Ozon: sending price to server...");
      await SHOPSPY.sendPrice(PLATFORM, productId, name, price, originalPrice);
    } else {
      console.log("ShopSpy Ozon: price is null, NOT sending");
    }

    const h = await SHOPSPY.getHistory(PLATFORM, productId);
    console.log("ShopSpy Ozon: history =", h);

    const trackingStatus = await SHOPSPY.checkTracking(PLATFORM, productId);
    SHOPSPY.isTracking = trackingStatus.tracking;
    SHOPSPY.trackingChatId = trackingStatus.chatId;

    SHOPSPY.renderPanel({
      history: h.history,
      analysis: h.analysis,
      reviews: null,
      productName: name,
      price,
      originalPrice,
      platform: PLATFORM,
      productId,
      getReviews,
    });
  }

  let lastUrl = "";
  setInterval(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      if (getProductId()) setTimeout(init, 1500);
    }
  }, 1000);
  setTimeout(init, 2000);
})();
