/**
 * ShopSpy - Wildberries content script
 */
(function () {
  "use strict";
  const PLATFORM = "wb";

  function getProductId() {
    const m = window.location.pathname.match(/\/catalog\/(\d+)/);
    return m ? m[1] : null;
  }

  function getProductName() {
    // Новый селектор для WB
    for (const s of [
      "h2.productTitle--lfc4o",
      ".productTitle--lfc4o",
      "h1.product-page__title",
      ".product-page__header h1",
      "h1",
    ]) {
      const el = document.querySelector(s);
      if (el && el.textContent.trim().length > 3) return el.textContent.trim();
    }
    return document.title.split(/[-|]/)[0].trim();
  }

  function getCurrentPrice() {
    console.log("ShopSpy WB: getCurrentPrice called");

    for (const s of [
      "ins.priceBlockFinalPrice--iToZR",
      ".priceBlockFinalPrice--iToZR",
      ".price-block__final-price",
    ]) {
      const el = document.querySelector(s);
      console.log('ShopSpy WB: selector "' + s + '" =>', el);
      if (el) {
        console.log("ShopSpy WB: element text =", el.textContent);
        const v = parseFloat(el.textContent.replace(/[^\d]/g, ""));
        console.log("ShopSpy WB: parsed value =", v);
        if (v > 0) return v;
      }
    }
    return null;
  }

  function getOriginalPrice() {
    // Новый селектор для WB
    for (const s of [
      "span.priceBlockOldPrice--qSWAf",
      ".priceBlockOldPrice--qSWAf",
      ".price-block__old-price del",
    ]) {
      const el = document.querySelector(s);
      if (el) {
        const v = parseFloat(el.textContent.replace(/[^\d]/g, ""));
        if (v > 0) return v;
      }
    }
    return null;
  }

  function getReviews() {
    const r = [];
    document
      .querySelectorAll(
        '.feedback__text, .comments__item__text, [data-link="text{:comment^text}"]',
      )
      .forEach((el) => {
        const t = el.textContent.trim();
        if (t.length > 10) r.push(t);
      });
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

  let lastUrl = "";
  setInterval(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      if (getProductId()) setTimeout(init, 1500);
    }
  }, 1000);
  setTimeout(init, 2000);
})();
