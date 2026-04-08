/**
 * ShopSpy - Ozon content script
 *
 * Парсинг цен на Ozon:
 * - Основная цена (без скидки Ozon Банка)
 * - Зачёркнутая старая цена
 */
(function () {
  "use strict";
  const PLATFORM = "ozon";

  /**
   * Извлекает число из строки цены.
   * "26 990 ₽" → 26990
   */
  function parsePrice(text) {
    if (!text) return null;
    // Удаляем всё кроме цифр
    const cleaned = text.replace(/[^\d]/g, "");
    const v = parseFloat(cleaned);
    return v > 0 && v < 100_000_000 ? v : null;
  }

  /**
   * Находит все цены в элементе и возвращает массив чисел.
   */
  function extractAllPrices(element) {
    const prices = [];
    const text = element.textContent || "";
    // Ищем все паттерны цен: число + ₽
    const matches = text.matchAll(/(\d[\d\s\u00a0\u2009]*)\s*₽/g);
    for (const match of matches) {
      const v = parsePrice(match[1]);
      if (v) prices.push(v);
    }
    return prices;
  }

  function getProductId() {
    // /product/nazvanie-12345/ или /product/12345/
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

    // Основной виджет с ценой
    const webPrice = document.querySelector('[data-widget="webPrice"]');
    if (!webPrice) {
      console.log("ShopSpy Ozon: webPrice widget not found");
      return null;
    }

    // Способ 1: Ищем контейнер с текстом "без Ozon Банка"
    const allSpans = webPrice.querySelectorAll("span");
    for (const span of allSpans) {
      const text = span.textContent || "";
      if (text.includes("без") && text.includes("Банка")) {
        // Цена в соседнем или родительском элементе
        const parent = span.parentElement;
        if (parent) {
          const prices = extractAllPrices(parent);
          console.log("ShopSpy Ozon: prices near 'без Банка' =", prices);
          if (prices.length > 0) return prices[0];
        }
      }
    }

    // Способ 2: Анализируем структуру webPrice
    // Обычно: первая цена = со скидкой банка, вторая = обычная
    const allPrices = extractAllPrices(webPrice);
    console.log("ShopSpy Ozon: all extracted prices =", allPrices);

    if (allPrices.length >= 2) {
      // Если 2+ цены, берём вторую (обычная цена без банка)
      // Сортируем по убыванию и берём вторую по величине или вторую по порядку
      return allPrices[1];
    }
    if (allPrices.length === 1) {
      return allPrices[0];
    }

    // Способ 3: Прямой поиск по селекторам цены
    for (const s of [
      '[data-widget="webPrice"] .m4_9',
      '[data-widget="webPrice"] [class*="m4_"]',
    ]) {
      const el = document.querySelector(s);
      if (el) {
        const v = parsePrice(el.textContent);
        if (v) {
          console.log("ShopSpy Ozon: found via selector", s, "=", v);
          return v;
        }
      }
    }

    console.log("ShopSpy Ozon: price not found");
    return null;
  }

  function getOriginalPrice() {
    console.log("ShopSpy Ozon: getOriginalPrice called");

    // Ищем зачёркнутую цену (старая цена до скидки)
    for (const s of [
      '[data-widget="webPrice"] s',
      '[data-widget="webPrice"] del',
      '[data-widget="webPrice"] span[style*="line-through"]',
      '[data-widget="webPrice"] [class*="b9i"]',
    ]) {
      const el = document.querySelector(s);
      if (el) {
        const v = parsePrice(el.textContent);
        console.log("ShopSpy Ozon: oldPrice via", s, "=", v);
        if (v) return v;
      }
    }

    // Альтернатива: ищем элемент с классом зачёркнутой цены
    const oldEl = document.querySelector(".pdp_bj.pdp_b0j.pdp_b9i, .pdp_b9i");
    if (oldEl) {
      const v = parsePrice(oldEl.textContent);
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
