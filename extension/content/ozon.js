/**
 * ShopSpy - Ozon content script
 *
 * Парсинг цен на Ozon:
 * - card_price: Цена по карте Ozon Банка (самая низкая)
 * - price: Цена без карты Ozon (со скидкой)
 * - original_price: Зачёркнутая цена без скидки
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

  /**
   * Извлекает все три цены с страницы Ozon.
   * Возвращает объект { card_price, price, original_price }
   */
  function getAllPrices() {
    console.log("ShopSpy Ozon: getAllPrices called");

    const result = {
      card_price: null, // Цена по Ozon карте
      price: null, // Цена без Ozon карты
      original_price: null, // Зачёркнутая цена без скидки
    };

    // Основной виджет с ценой
    const webPrice = document.querySelector('[data-widget="webPrice"]');
    if (!webPrice) {
      console.log("ShopSpy Ozon: webPrice widget not found");
      return result;
    }

    // ── 1. Ищем цену по Ozon карте ──
    // Структура: <span class="tsHeadline600Large">4 090 ₽</span> рядом с текстом "c Ozon Банком"
    const cardPriceSelectors = [
      ".pdp_i1b .tsHeadline600Large",
      ".pdp_ib1 .tsHeadline600Large",
      ".pdp_b1i .tsHeadline600Large",
    ];

    for (const selector of cardPriceSelectors) {
      const el = webPrice.querySelector(selector);
      if (el) {
        const v = parsePrice(el.textContent);
        if (v) {
          result.card_price = v;
          console.log("ShopSpy Ozon: card_price found via", selector, "=", v);
          break;
        }
      }
    }

    // Альтернативный способ: ищем блок с текстом "c Ozon Банком"
    if (!result.card_price) {
      const allSpans = webPrice.querySelectorAll("span");
      for (const span of allSpans) {
        const text = span.textContent || "";
        if (text.includes("Ozon Банк") || text.includes("Ozon Банком")) {
          // Ищем цену в родительском элементе
          const parent = span.closest(".pdp_ib1, .pdp_b1i, .pdp_i0b");
          if (parent) {
            const priceEl = parent.querySelector(
              ".tsHeadline600Large, .tsHeadline500Large",
            );
            if (priceEl) {
              const v = parsePrice(priceEl.textContent);
              if (v) {
                result.card_price = v;
                console.log(
                  "ShopSpy Ozon: card_price found near 'Ozon Банк' =",
                  v,
                );
                break;
              }
            }
          }
        }
      }
    }

    // ── 2. Ищем цену без Ozon карты (основная цена со скидкой) ──
    // Структура: <span class="pdp_bj tsHeadline500Medium">4 470 ₽</span>
    const priceSelectors = [
      ".pdp_bj.tsHeadline500Medium",
      ".pdp_jb1 > .pdp_bj",
      ".pdp_b9i .pdp_bj",
    ];

    for (const selector of priceSelectors) {
      const el = webPrice.querySelector(selector);
      if (el) {
        const v = parsePrice(el.textContent);
        if (v) {
          result.price = v;
          console.log("ShopSpy Ozon: price found via", selector, "=", v);
          break;
        }
      }
    }

    // Альтернативный способ: ищем блок с текстом "без Ozon Банка"
    if (!result.price) {
      const allSpans = webPrice.querySelectorAll("span");
      for (const span of allSpans) {
        const text = span.textContent || "";
        if (text.includes("без") && text.includes("Банка")) {
          // Цена в родительском контейнере
          const parent = span.closest(".pdp_b1j, .pdp_jb1");
          if (parent) {
            // Ищем элемент с классом pdp_bj (основная цена)
            const priceEl = parent.querySelector(".pdp_bj");
            if (priceEl && !priceEl.classList.contains("pdp_bj0")) {
              const v = parsePrice(priceEl.textContent);
              if (v) {
                result.price = v;
                console.log("ShopSpy Ozon: price found near 'без Банка' =", v);
                break;
              }
            }
          }
        }
      }
    }

    // ── 3. Ищем зачёркнутую цену (original_price) ──
    // Структура: <span class="pdp_i9b pdp_bj0 pdp_bi9 tsBody400Small">4 795 ₽</span>
    const originalPriceSelectors = [
      ".pdp_i9b.pdp_bj0",
      ".pdp_bj0.pdp_bi9",
      ".pdp_jb1 > .pdp_i9b",
    ];

    for (const selector of originalPriceSelectors) {
      const el = webPrice.querySelector(selector);
      if (el) {
        const v = parsePrice(el.textContent);
        if (v) {
          result.original_price = v;
          console.log(
            "ShopSpy Ozon: original_price found via",
            selector,
            "=",
            v,
          );
          break;
        }
      }
    }

    // Альтернативный способ: ищем через зачёркнутый текст
    if (!result.original_price) {
      for (const s of ["s", "del", 'span[style*="line-through"]']) {
        const el = webPrice.querySelector(s);
        if (el) {
          const v = parsePrice(el.textContent);
          if (v) {
            result.original_price = v;
            console.log("ShopSpy Ozon: original_price via", s, "=", v);
            break;
          }
        }
      }
    }

    // ── Логика определения цен если не все найдены ──
    // Если нашли только 2 цены, определяем какая какая
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
      console.log(
        "ShopSpy Ozon: original_price <= price, swapping or clearing",
      );
      result.original_price = null;
    }
    if (
      result.price &&
      result.card_price &&
      result.price <= result.card_price
    ) {
      console.log("ShopSpy Ozon: price <= card_price, clearing card_price");
      result.card_price = null;
    }

    console.log("ShopSpy Ozon: final prices =", result);
    return result;
  }

  /**
   * Возвращает основную цену (без Ozon карты) для совместимости
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

    const prices = getAllPrices();
    const name = getProductName();

    console.log("ShopSpy Ozon: card_price =", prices.card_price);
    console.log("ShopSpy Ozon: price =", prices.price);
    console.log("ShopSpy Ozon: original_price =", prices.original_price);
    console.log("ShopSpy Ozon: name =", name);

    // Используем основную цену (без карты) как price, или card_price если нет основной
    const mainPrice = prices.price || prices.card_price;

    if (mainPrice) {
      console.log("ShopSpy Ozon: sending prices to server...");
      await SHOPSPY.sendPrice(
        PLATFORM,
        productId,
        name,
        mainPrice,
        prices.original_price,
        prices.card_price,
      );
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
      price: mainPrice,
      originalPrice: prices.original_price,
      cardPrice: prices.card_price,
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
