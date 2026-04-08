/**
 * ShopSpy - Wildberries content script
 *
 * Парсинг цен на Wildberries:
 * - Текущая цена (со скидкой)
 * - Оригинальная цена (зачёркнутая)
 */
(function () {
  "use strict";
  const PLATFORM = "wb";

  /**
   * Извлекает число из строки цены.
   * "1 299 ₽" → 1299
   */
  function parsePrice(text) {
    if (!text) return null;
    // Удаляем всё кроме цифр
    const cleaned = text.replace(/[^\d]/g, "");
    const v = parseFloat(cleaned);
    return v > 0 && v < 100_000_000 ? v : null;
  }

  function getProductId() {
    // /catalog/123456789/detail.aspx или /catalog/123456789/
    const m = window.location.pathname.match(/\/catalog\/(\d+)/);
    return m ? m[1] : null;
  }

  function getProductName() {
    // Актуальные селекторы WB (могут меняться)
    for (const s of [
      // Новый дизайн
      "h2.productTitle--lfc4o",
      ".productTitle--lfc4o",
      // Старый дизайн
      "h1.product-page__title",
      ".product-page__header h1",
      // Fallback
      "h1",
    ]) {
      const el = document.querySelector(s);
      if (el && el.textContent.trim().length > 3) {
        return el.textContent.trim();
      }
    }
    return document.title.split(/[-|]/)[0].trim();
  }

  function getCurrentPrice() {
    console.log("ShopSpy WB: getCurrentPrice called");

    // Способ 1: Прямые селекторы цены (приоритет)
    for (const s of [
      // Новый дизайн
      "ins.priceBlockFinalPrice--iToZR",
      ".priceBlockFinalPrice--iToZR",
      // Старый дизайн
      ".price-block__final-price",
      "span.price-block__final-price",
      // Альтернативные
      "[class*='final-price']",
      "[class*='FinalPrice']",
    ]) {
      const el = document.querySelector(s);
      if (el) {
        const v = parsePrice(el.textContent);
        console.log('ShopSpy WB: selector "' + s + '" =>', v);
        if (v) return v;
      }
    }

    // Способ 2: Ищем в блоке цен элемент с наибольшей ценой (не зачёркнутый)
    const priceBlock = document.querySelector(
      ".price-block, .product-price, [class*='priceBlock']",
    );
    if (priceBlock) {
      // Ищем все элементы с ценой, которые НЕ зачёркнуты
      const priceElements = priceBlock.querySelectorAll(
        "span, ins, div:not([style*='line-through']):not(s):not(del)",
      );
      let maxPrice = null;
      for (const el of priceElements) {
        // Пропускаем зачёркнутые
        const style = window.getComputedStyle(el);
        if (style.textDecoration.includes("line-through")) continue;

        const v = parsePrice(el.textContent);
        if (v && (!maxPrice || v > maxPrice)) {
          maxPrice = v;
        }
      }
      if (maxPrice) {
        console.log(
          "ShopSpy WB: found price via priceBlock search =",
          maxPrice,
        );
        return maxPrice;
      }
    }

    // Способ 3: Поиск по тексту с ₽
    const allText = document.body.innerText;
    const priceMatches = allText.match(/(\d[\d\s]*)\s*₽/g);
    if (priceMatches) {
      // Ищем цену в основном блоке товара
      const mainContent = document.querySelector(
        ".product-page, .product-detail, main, [class*='product']",
      );
      if (mainContent) {
        const prices = [];
        const walker = document.createTreeWalker(
          mainContent,
          NodeFilter.SHOW_TEXT,
          null,
          false,
        );
        let node;
        while ((node = walker.nextNode())) {
          const text = node.textContent;
          const match = text.match(/(\d[\d\s]*)\s*₽/);
          if (match) {
            const v = parsePrice(match[1]);
            if (v) prices.push(v);
          }
        }
        if (prices.length > 0) {
          // Берём последнюю найденную цену (обычно текущая)
          console.log("ShopSpy WB: all found prices =", prices);
          return prices[prices.length - 1];
        }
      }
    }

    console.log("ShopSpy WB: price not found");
    return null;
  }

  function getOriginalPrice() {
    console.log("ShopSpy WB: getOriginalPrice called");

    // Ищем зачёркнутую старую цену
    for (const s of [
      // Новый дизайн
      "span.priceBlockOldPrice--qSWAf",
      ".priceBlockOldPrice--qSWAf",
      // Старый дизайн
      ".price-block__old-price del",
      ".price-block__old-price",
      // Зачёркнутые элементы
      "del.price",
      "s.price",
      "[class*='old-price']",
      "[class*='oldPrice']",
    ]) {
      const el = document.querySelector(s);
      if (el) {
        const v = parsePrice(el.textContent);
        if (v) {
          console.log('ShopSpy WB: oldPrice via "' + s + '" =', v);
          return v;
        }
      }
    }

    // Ищем по стилю line-through в блоке цен
    const priceBlock = document.querySelector(
      ".price-block, .product-price, [class*='priceBlock']",
    );
    if (priceBlock) {
      const struckElements = priceBlock.querySelectorAll(
        "s, del, span[style*='line-through'], [class*='old']",
      );
      for (const el of struckElements) {
        const v = parsePrice(el.textContent);
        if (v) {
          console.log("ShopSpy WB: oldPrice via line-through =", v);
          return v;
        }
      }
    }

    return null;
  }

  function getReviews() {
    const r = [];
    // Актуальные селекторы отзывов WB
    for (const s of [
      ".feedback__text",
      ".comments__item__text",
      "[data-link='text{:comment^text}']",
      ".review__text",
      "[class*='feedback'] span",
    ]) {
      document.querySelectorAll(s).forEach((el) => {
        const t = el.textContent.trim();
        if (t.length > 10 && !r.includes(t)) {
          r.push(t);
        }
      });
      if (r.length > 0) break;
    }
    return r;
  }

  async function init() {
    console.log("ShopSpy WB: init started");

    const productId = getProductId();
    console.log("ShopSpy WB: productId =", productId);

    if (!productId) {
      console.log("ShopSpy WB: no productId, exit");
      return;
    }

    SHOPSPY.createPanel();

    const price = getCurrentPrice();
    const originalPrice = getOriginalPrice();
    const name = getProductName();

    console.log("ShopSpy WB: price =", price);
    console.log("ShopSpy WB: originalPrice =", originalPrice);
    console.log("ShopSpy WB: name =", name);

    if (price) {
      console.log("ShopSpy WB: sending price to server...");
      await SHOPSPY.sendPrice(PLATFORM, productId, name, price, originalPrice);
    } else {
      console.log("ShopSpy WB: price is null, NOT sending");
    }

    const h = await SHOPSPY.getHistory(PLATFORM, productId);
    console.log("ShopSpy WB: history =", h);

    // Проверяем статус отслеживания
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

  // Отслеживание изменения URL (SPA навигация)
  let lastUrl = "";
  setInterval(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      if (getProductId()) {
        setTimeout(init, 1500);
      }
    }
  }, 1000);

  // Начальная инициализация
  setTimeout(init, 2000);
})();
