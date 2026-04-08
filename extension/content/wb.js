/**
 * ShopSpy - Wildberries content script
 *
 * Парсинг цен на Wildberries:
 * - card_price: Цена с WB Кошельком (самая низкая)
 * - price: Цена без WB Кошелька (со скидкой)
 * - original_price: Зачёркнутая цена без скидки
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

  /**
   * Извлекает все три цены с страницы Wildberries.
   * Возвращает объект { card_price, price, original_price }
   */
  function getAllPrices() {
    console.log("ShopSpy WB: getAllPrices called");

    const result = {
      card_price: null, // Цена с WB Кошельком
      price: null, // Цена без WB Кошелька
      original_price: null, // Зачёркнутая цена без скидки
    };

    // ── 1. Ищем цену с WB Кошельком ──
    // Структура: <div class="walletPriceWrap--GjYV7"><h2 class="...color_danger">19 870 ₽</h2>
    const walletPriceSelectors = [
      '[class*="walletPriceWrap"] h2',
      '[class*="walletPrice"] h2.mo-typography_color_danger',
      ".walletPriceWrap--GjYV7 h2",
      '[class*="walletPriceWrap"] .mo-typography_color_danger',
    ];

    for (const selector of walletPriceSelectors) {
      const el = document.querySelector(selector);
      if (el) {
        const v = parsePrice(el.textContent);
        if (v) {
          result.card_price = v;
          console.log("ShopSpy WB: card_price found via", selector, "=", v);
          break;
        }
      }
    }

    // Альтернативный способ: ищем по тексту "с WB Кошельком"
    if (!result.card_price) {
      const allElements = document.querySelectorAll("span, h2, h3");
      for (const el of allElements) {
        const text = el.textContent || "";
        if (text.includes("WB Кошельком") || text.includes("с кошельком")) {
          // Цена в соседнем или родительском элементе
          const parent = el.closest('[class*="walletPrice"], [class*="slide"]');
          if (parent) {
            const priceEl = parent.querySelector(
              "h2, .mo-typography_variant_title2",
            );
            if (priceEl && priceEl !== el) {
              const v = parsePrice(priceEl.textContent);
              if (v) {
                result.card_price = v;
                console.log(
                  "ShopSpy WB: card_price found near 'WB Кошельком' =",
                  v,
                );
                break;
              }
            }
          }
        }
      }
    }

    // ── 2. Ищем цену без WB Кошелька (основная цена со скидкой) ──
    // Структура: <div class="finalPriceWrap--tKHRP"><h2>20 485 ₽</h2>
    const priceSelectors = [
      '[class*="finalPriceWrap"] h2.mo-typography_color_primary',
      '[class*="finalPriceWrap"] h2',
      ".finalPriceWrap--tKHRP h2",
      '[class*="finalPriceBlock"] h2',
      ".finalPriceBlock--WasTo h2",
    ];

    for (const selector of priceSelectors) {
      const el = document.querySelector(selector);
      if (el) {
        const v = parsePrice(el.textContent);
        if (v) {
          result.price = v;
          console.log("ShopSpy WB: price found via", selector, "=", v);
          break;
        }
      }
    }

    // Альтернативный способ: ищем по тексту "без WB Кошелька"
    if (!result.price) {
      const allElements = document.querySelectorAll("span");
      for (const el of allElements) {
        const text = el.textContent || "";
        if (text.includes("без") && text.includes("Кошелька")) {
          // Цена в соседнем или родительском элементе
          const parent = el.closest('[class*="finalPrice"], [class*="slide"]');
          if (parent) {
            const priceEl = parent.querySelector(
              "h2, .mo-typography_variant_title2",
            );
            if (priceEl && priceEl !== el) {
              const v = parsePrice(priceEl.textContent);
              if (v) {
                result.price = v;
                console.log("ShopSpy WB: price found near 'без Кошелька' =", v);
                break;
              }
            }
          }
        }
      }
    }

    // Fallback: старые селекторы
    if (!result.price) {
      for (const s of [
        "ins.priceBlockFinalPrice--iToZR",
        ".priceBlockFinalPrice--iToZR",
        ".price-block__final-price",
        "span.price-block__final-price",
        "[class*='final-price']",
        "[class*='FinalPrice']",
      ]) {
        const el = document.querySelector(s);
        if (el) {
          const v = parsePrice(el.textContent);
          if (v) {
            result.price = v;
            console.log("ShopSpy WB: price via fallback", s, "=", v);
            break;
          }
        }
      }
    }

    // ── 3. Ищем зачёркнутую цену (original_price) ──
    // Структура: <span class="mo-typography_variant_body-strikethrough">33 321 ₽</span>
    const originalPriceSelectors = [
      ".mo-typography_variant_body-strikethrough",
      '[class*="finalPriceBlock"] .mo-typography_variant_body-strikethrough',
      ".finalPriceBlock--WasTo .mo-typography_variant_body-strikethrough",
      '[class*="strikethrough"]',
    ];

    for (const selector of originalPriceSelectors) {
      const el = document.querySelector(selector);
      if (el) {
        const v = parsePrice(el.textContent);
        if (v) {
          result.original_price = v;
          console.log("ShopSpy WB: original_price found via", selector, "=", v);
          break;
        }
      }
    }

    // Альтернативный способ: ищем через зачёркнутый текст или старые селекторы
    if (!result.original_price) {
      for (const s of [
        "span.priceBlockOldPrice--qSWAf",
        ".priceBlockOldPrice--qSWAf",
        ".price-block__old-price del",
        ".price-block__old-price",
        "del.price",
        "s.price",
        "[class*='old-price']",
        "[class*='oldPrice']",
        "s",
        "del",
      ]) {
        const el = document.querySelector(s);
        if (el) {
          const v = parsePrice(el.textContent);
          if (v) {
            result.original_price = v;
            console.log("ShopSpy WB: original_price via fallback", s, "=", v);
            break;
          }
        }
      }
    }

    // ── Логика определения цен если не все найдены ──
    const foundPrices = [
      result.card_price,
      result.price,
      result.original_price,
    ].filter((p) => p !== null);

    if (foundPrices.length === 1 && !result.price) {
      // Если нашли только одну цену - это основная
      result.price = foundPrices[0];
      result.card_price = null;
      result.original_price = null;
    } else if (foundPrices.length === 2) {
      // Если две цены - меньшая это card_price, большая это price или original_price
      const sorted = foundPrices.sort((a, b) => a - b);
      if (!result.card_price && !result.price) {
        result.card_price = sorted[0];
        result.price = sorted[1];
      } else if (!result.price && !result.original_price) {
        result.price = sorted[0];
        result.original_price = sorted[1];
      }
    }

    // Валидация: original_price должна быть больше price, price больше card_price
    if (
      result.original_price &&
      result.price &&
      result.original_price <= result.price
    ) {
      console.log("ShopSpy WB: original_price <= price, clearing");
      result.original_price = null;
    }
    if (
      result.price &&
      result.card_price &&
      result.price <= result.card_price
    ) {
      console.log("ShopSpy WB: price <= card_price, clearing card_price");
      result.card_price = null;
    }

    console.log("ShopSpy WB: final prices =", result);
    return result;
  }

  /**
   * Возвращает основную цену (без WB Кошелька) для совместимости
   */
  function getCurrentPrice() {
    const prices = getAllPrices();
    return prices.price || prices.card_price;
  }

  /**
   * Возвращает зачёркнутую цену
   */
  function getOriginalPrice() {
    const prices = getAllPrices();
    return prices.original_price;
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

    const prices = getAllPrices();
    const name = getProductName();

    console.log("ShopSpy WB: card_price =", prices.card_price);
    console.log("ShopSpy WB: price =", prices.price);
    console.log("ShopSpy WB: original_price =", prices.original_price);
    console.log("ShopSpy WB: name =", name);

    // Используем основную цену (без кошелька) как price, или card_price если нет основной
    const mainPrice = prices.price || prices.card_price;

    if (mainPrice) {
      console.log("ShopSpy WB: sending prices to server...");
      await SHOPSPY.sendPrice(
        PLATFORM,
        productId,
        name,
        mainPrice,
        prices.original_price,
        prices.card_price,
      );
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
      price: mainPrice,
      originalPrice: prices.original_price,
      cardPrice: prices.card_price,
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
