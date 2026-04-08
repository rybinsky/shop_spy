/*
 * ShopSpy Mini App
 * Дашборд со статистикой, свайпами между экранами и нижней навигацией.
 */

(function () {
  "use strict";

  const DEFAULT_API_BASE = "";
  const STORAGE_KEY_API_BASE = "shopspy_api_base";
  const VIEWS = ["overview", "products", "purchases", "activity"];
  const PRICE_PRESET_CURRENT = "current";
  const PRICE_PRESET_CARD = "card";
  const PRICE_PRESET_CUSTOM = "custom";

  const state = {
    telegramId: null,
    summary: null,
    products: [],
    activity: [],
    purchases: [],
    activeViewIndex: 0,
    activeModalProduct: null,
    selectedPricePreset: PRICE_PRESET_CURRENT,
  };

  /* ── Helpers ── */

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMoney(v) {
    if (v === null || v === undefined || v === "") return "—";
    const n = Number(v);
    if (Number.isNaN(n)) return "—";
    return `${Math.round(n).toLocaleString("ru")} ₽`;
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("ru");
  }

  function formatDateForInput(value) {
    if (!value) return new Date().toISOString().slice(0, 10);
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return new Date().toISOString().slice(0, 10);
    return date.toISOString().slice(0, 10);
  }

  function platformLabel(platform) {
    if (platform === "wb") return { text: "WB", cls: "wb" };
    if (platform === "ozon") return { text: "Ozon", cls: "ozon" };
    return { text: platform || "?", cls: "" };
  }

  function getQueryParam(name) {
    const url = new URL(window.location.href);
    return url.searchParams.get(name);
  }

  function getTelegramIdFromWebApp() {
    try {
      if (window.Telegram && Telegram.WebApp) {
        Telegram.WebApp.ready();
        Telegram.WebApp.expand();
        const user = Telegram.WebApp.initDataUnsafe?.user;
        if (user && user.id) return Number(user.id);
      }
    } catch (e) {
      // ignore
    }
    return null;
  }

  function getApiBase() {
    const fromQuery = getQueryParam("api");
    if (fromQuery) {
      localStorage.setItem(STORAGE_KEY_API_BASE, fromQuery);
      return fromQuery;
    }
    return localStorage.getItem(STORAGE_KEY_API_BASE) || DEFAULT_API_BASE;
  }

  async function apiGet(path) {
    const url = `${getApiBase()}${path}`;
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`HTTP ${response.status} for ${path}: ${text}`);
    }
    return await response.json();
  }

  async function apiPost(path, payload) {
    const url = `${getApiBase()}${path}`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`HTTP ${response.status} for ${path}: ${text}`);
    }
    return await response.json();
  }

  /* ── Badge ── */

  function getHeroBadge(summary) {
    if (!summary) return "Новичок";
    if ((summary.real_saved_total || 0) >= 10000) return "Мастер экономии";
    if ((summary.purchased_count || 0) >= 3) return "Практичный покупатель";
    if ((summary.total_viewed || 0) >= 20) return "Охотник за скидками";
    return "Новичок";
  }

  /* ── Build views ── */

  function buildOverview() {
    const summary = state.summary || {};
    const best = summary.best_deal;
    const recentProducts = state.products.slice(0, 3).map(buildProductCard).join("");

    return `
      <section class="hero">
        <div class="hero-top">
          <div>
            <div class="hero-label">${getHeroBadge(summary)}</div>
            <div class="hero-title">Твоя выгода под контролем</div>
            <div class="hero-subtitle">ShopSpy считает просмотры, покупки и реальную экономию.</div>
          </div>
          <div class="hero-icon">🔍</div>
        </div>
        <div class="hero-metrics">
          <div class="hero-metric">
            <span>Потенциально сэкономлено</span>
            <b>${formatMoney(summary.total_saved)}</b>
          </div>
          <div class="hero-metric">
            <span>Реально сэкономлено</span>
            <b>${formatMoney(summary.real_saved_total)}</b>
          </div>
        </div>
      </section>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-title">Просмотрено</div>
          <div class="stat-value">${summary.total_viewed || 0}</div>
          <div class="stat-hint">уникальных карточек</div>
        </div>
        <div class="stat-card">
          <div class="stat-title">Покупок</div>
          <div class="stat-value">${summary.purchased_count || 0}</div>
          <div class="stat-hint">сохранено вручную</div>
        </div>
        <div class="stat-card">
          <div class="stat-title">За месяц</div>
          <div class="stat-value">${summary.monthly_views || 0}</div>
          <div class="stat-hint">просмотров</div>
        </div>
        <div class="stat-card">
          <div class="stat-title">Выгода за месяц</div>
          <div class="stat-value accent">${formatMoney(summary.monthly_saved)}</div>
          <div class="stat-hint">по цене ниже средней</div>
        </div>
      </div>

      <div class="quick-actions">
        <button class="quick-btn" data-view-jump="products">🛍 Товары</button>
        <button class="quick-btn" data-view-jump="purchases">✅ Покупки</button>
        <button class="quick-btn" data-view-jump="activity">📈 Активность</button>
      </div>

      ${best ? `
        <section class="panel">
          <div class="section-title">Лучшая находка</div>
          <div class="best-card">
            <div class="best-name">${escapeHtml(best.product_name || best.product_id)}</div>
            <div class="best-meta">${platformLabel(best.platform).text} · Экономия ${formatMoney(best.saved_amount)}</div>
          </div>
        </section>
      ` : ""}

      <section class="panel">
        <div class="section-head">
          <div class="section-title">Свежие товары</div>
          <button class="link-btn" data-view-jump="products">Все</button>
        </div>
        <div class="stack">${recentProducts || `<div class="empty-state">Пока пусто — открой товары в расширении.</div>`}</div>
      </section>
    `;
  }

  function buildProductCard(product) {
    const pl = platformLabel(product.platform);
    const title = escapeHtml(product.product_name || product.product_id);
    const purchaseInfo = product.purchase_price
      ? `
        <div class="purchase-banner">
          ✅ Куплено за <b>${formatMoney(product.purchase_price)}</b>
          <span>· ${formatDateTime(product.purchased_at)}</span>
        </div>
      `
      : "";

    return `
      <article class="product-card">
        <div class="product-head">
          <div class="product-name">${title}</div>
          <div class="pill ${pl.cls}">${pl.text}</div>
        </div>
        <div class="meta-row">
          <span>Цена <b>${formatMoney(product.price)}</b></span>
          <span>По карте <b>${formatMoney(product.card_price)}</b></span>
        </div>
        <div class="meta-row">
          <span>Средняя <b>${formatMoney(product.avg_price)}</b></span>
          <span>Экономия <b class="money-positive">${formatMoney(product.saved_amount)}</b></span>
        </div>
        <div class="meta-row muted-row">
          <span>Последний просмотр: <b>${formatDateTime(product.last_view)}</b></span>
        </div>
        ${purchaseInfo}
        <div class="card-actions">
          <button class="action-btn primary" data-action="buy" data-platform="${product.platform}" data-product-id="${escapeHtml(product.product_id)}">✅ Купил</button>
        </div>
      </article>
    `;
  }

  function buildProducts() {
    return `
      <section class="panel">
        <div class="section-title">Мои товары</div>
        <div class="stack">
          ${state.products.length ? state.products.map(buildProductCard).join("") : `<div class="empty-state">Пока нет товаров — сначала открой их в расширении.</div>`}
        </div>
      </section>
    `;
  }

  function buildPurchaseCard(purchase) {
    const pl = platformLabel(purchase.platform);
    return `
      <article class="product-card">
        <div class="product-head">
          <div class="product-name">${escapeHtml(purchase.product_name || purchase.product_id)}</div>
          <div class="pill ${pl.cls}">${pl.text}</div>
        </div>
        <div class="meta-row">
          <span>Куплено за <b>${formatMoney(purchase.purchase_price)}</b></span>
          <span>Средняя <b>${formatMoney(purchase.avg_price)}</b></span>
        </div>
        <div class="meta-row">
          <span>Сэкономлено от средней <b class="money-positive">${formatMoney(purchase.saved_vs_avg)}</b></span>
          <span>От зачёркнутой <b class="money-positive">${formatMoney(purchase.saved_vs_original)}</b></span>
        </div>
        <div class="meta-row muted-row">
          <span>Дата покупки: <b>${formatDateTime(purchase.purchased_at)}</b></span>
        </div>
      </article>
    `;
  }

  function buildPurchases() {
    return `
      <section class="panel">
        <div class="section-head">
          <div class="section-title">Мои покупки</div>
          <div class="section-note">Реальная экономия по введённой цене</div>
        </div>
        <div class="stack">
          ${state.purchases.length ? state.purchases.map(buildPurchaseCard).join("") : `<div class="empty-state">Пока нет покупок — нажми «Купил» у нужного товара.</div>`}
        </div>
      </section>
    `;
  }

  function buildActivity() {
    const rows = state.activity.slice(0, 30);
    return `
      <section class="panel">
        <div class="section-title">Активность</div>
        <div class="stack">
          ${rows.length
            ? rows.map((row) => `
                <article class="activity-card">
                  <div class="product-head">
                    <div class="product-name">${escapeHtml(row.date)}</div>
                    <div class="pill">${row.views} просмотров</div>
                  </div>
                  <div class="meta-row">
                    <span>Экономия <b class="money-positive">${formatMoney(row.saved)}</b></span>
                  </div>
                </article>
              `).join("")
            : `<div class="empty-state">Активности пока нет.</div>`
          }
        </div>
      </section>
    `;
  }

  /* ── Rendering ── */

  const viewBuilders = [buildOverview, buildProducts, buildPurchases, buildActivity];

  function renderRoot() {
    $("subtitle").textContent = `Telegram ID: ${state.telegramId}`;
    $("bottom-nav").style.display = "";

    // Build all 4 pages for swipe
    const pages = viewBuilders.map((builder, i) => {
      return `<div class="swipe-page" data-page="${i}"><div class="view-content">${builder()}</div></div>`;
    }).join("");

    $("root").innerHTML = `
      <div class="swipe-container" id="swipe-container">
        <div class="swipe-track" id="swipe-track">${pages}</div>
      </div>
    `;

    updateSwipePosition(false);
    updateBottomNav();
    bindCommonEvents();
    initSwipe();
  }

  function updateSwipePosition(animate) {
    const track = $("swipe-track");
    if (!track) return;
    if (animate) {
      track.classList.remove("swiping");
    } else {
      track.classList.add("swiping");
      // Force reflow, then remove to allow future animations
      void track.offsetWidth;
      track.classList.remove("swiping");
    }
    track.style.transform = `translateX(-${state.activeViewIndex * 100}%)`;
  }

  function updateBottomNav() {
    document.querySelectorAll(".nav-item").forEach((btn) => {
      const viewKey = btn.dataset.nav;
      const idx = VIEWS.indexOf(viewKey);
      btn.classList.toggle("active", idx === state.activeViewIndex);
    });
  }

  function setActiveView(viewKey) {
    const idx = VIEWS.indexOf(viewKey);
    if (idx === -1 || idx === state.activeViewIndex) return;
    state.activeViewIndex = idx;
    updateSwipePosition(true);
    updateBottomNav();
    // Scroll to top of new page
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function setActiveViewByIndex(idx) {
    if (idx < 0 || idx >= VIEWS.length || idx === state.activeViewIndex) return;
    state.activeViewIndex = idx;
    updateSwipePosition(true);
    updateBottomNav();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* ── Swipe handling ── */

  function initSwipe() {
    const container = $("swipe-container");
    if (!container) return;

    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let isDragging = false;
    let isHorizontal = null;
    const threshold = 50;

    container.addEventListener("touchstart", (e) => {
      // Don't swipe if modal is open
      if ($("purchase-modal").classList.contains("open")) return;
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      currentX = startX;
      isDragging = true;
      isHorizontal = null;
    }, { passive: true });

    container.addEventListener("touchmove", (e) => {
      if (!isDragging) return;
      currentX = e.touches[0].clientX;
      const diffX = currentX - startX;
      const diffY = e.touches[0].clientY - startY;

      // Determine direction on first significant move
      if (isHorizontal === null && (Math.abs(diffX) > 8 || Math.abs(diffY) > 8)) {
        isHorizontal = Math.abs(diffX) > Math.abs(diffY);
      }

      if (!isHorizontal) return;

      const track = $("swipe-track");
      // Prevent overscroll at edges
      if (state.activeViewIndex === 0 && diffX > 0) return;
      if (state.activeViewIndex === VIEWS.length - 1 && diffX < 0) return;

      track.classList.add("swiping");
      const baseOffset = -state.activeViewIndex * 100;
      const dragPercent = (diffX / container.offsetWidth) * 100;
      track.style.transform = `translateX(${baseOffset + dragPercent}%)`;
    }, { passive: true });

    container.addEventListener("touchend", () => {
      if (!isDragging) return;
      isDragging = false;

      if (!isHorizontal) return;

      const diffX = currentX - startX;
      const track = $("swipe-track");
      track.classList.remove("swiping");

      if (Math.abs(diffX) > threshold) {
        if (diffX < 0 && state.activeViewIndex < VIEWS.length - 1) {
          state.activeViewIndex++;
        } else if (diffX > 0 && state.activeViewIndex > 0) {
          state.activeViewIndex--;
        }
      }

      updateSwipePosition(true);
      updateBottomNav();
    }, { passive: true });
  }

  /* ── Purchase modal ── */

  function getProductByKey(platform, productId) {
    return state.products.find(
      (product) => product.platform === platform && String(product.product_id) === String(productId),
    );
  }

  function openPurchaseModal(platform, productId) {
    const product = getProductByKey(platform, productId);
    if (!product) return;

    state.activeModalProduct = product;
    state.selectedPricePreset = product.card_price ? PRICE_PRESET_CARD : PRICE_PRESET_CURRENT;

    const overlay = $("purchase-modal");
    const content = $("purchase-modal-content");
    const defaultPrice = product.card_price || product.price || "";

    content.innerHTML = `
      <div class="modal-header">
        <div>
          <div class="section-title">Отметить покупку</div>
          <div class="section-note">${escapeHtml(product.product_name || product.product_id)}</div>
        </div>
        <button class="icon-btn" id="purchase-close-btn">✕</button>
      </div>

      <div class="input-group">
        <label>Быстрая подстановка цены</label>
        <div class="preset-row">
          <button class="preset-btn ${state.selectedPricePreset === PRICE_PRESET_CURRENT ? "active" : ""}" data-preset="${PRICE_PRESET_CURRENT}">
            Текущая ${formatMoney(product.price)}
          </button>
          <button class="preset-btn ${state.selectedPricePreset === PRICE_PRESET_CARD ? "active" : ""}" data-preset="${PRICE_PRESET_CARD}" ${product.card_price ? "" : "disabled"}>
            По карте ${formatMoney(product.card_price)}
          </button>
          <button class="preset-btn ${state.selectedPricePreset === PRICE_PRESET_CUSTOM ? "active" : ""}" data-preset="${PRICE_PRESET_CUSTOM}">
            Своя цена
          </button>
        </div>
      </div>

      <div class="input-group">
        <label for="purchase-price-input">Цена покупки</label>
        <input id="purchase-price-input" class="text-input" type="number" min="1" step="1" value="${defaultPrice || ""}" placeholder="Введите цену" />
      </div>

      <div class="input-group">
        <label for="purchase-date-input">Дата покупки</label>
        <input id="purchase-date-input" class="text-input" type="date" value="${formatDateForInput(product.purchased_at)}" />
      </div>

      <div class="purchase-summary">
        <div>Средняя цена: <b>${formatMoney(product.avg_price)}</b></div>
        <div>Зачёркнутая: <b>${formatMoney(product.original_price)}</b></div>
      </div>

      <div id="purchase-error" class="form-error hidden"></div>

      <button class="save-btn" id="purchase-save-btn">Сохранить покупку</button>
    `;

    overlay.classList.add("open");
    bindPurchaseModalEvents(product);
  }

  function closePurchaseModal() {
    $("purchase-modal").classList.remove("open");
    $("purchase-modal-content").innerHTML = "";
    state.activeModalProduct = null;
  }

  function applyPreset(product, preset) {
    state.selectedPricePreset = preset;
    const input = $("purchase-price-input");
    if (!input) return;

    if (preset === PRICE_PRESET_CURRENT) input.value = product.price || "";
    if (preset === PRICE_PRESET_CARD) input.value = product.card_price || product.price || "";
    if (preset === PRICE_PRESET_CUSTOM && !input.value) input.value = "";

    $("purchase-modal-content")
      .querySelectorAll("[data-preset]")
      .forEach((btn) => btn.classList.toggle("active", btn.dataset.preset === preset));
  }

  function bindPurchaseModalEvents(product) {
    $("purchase-close-btn").addEventListener("click", closePurchaseModal);

    $("purchase-modal-content")
      .querySelectorAll("[data-preset]")
      .forEach((btn) => {
        btn.addEventListener("click", () => applyPreset(product, btn.dataset.preset));
      });

    $("purchase-save-btn").addEventListener("click", async () => {
      const priceInput = $("purchase-price-input");
      const dateInput = $("purchase-date-input");
      const errorBox = $("purchase-error");
      const saveBtn = $("purchase-save-btn");
      const purchasePrice = Number(priceInput.value);

      if (!purchasePrice || Number.isNaN(purchasePrice) || purchasePrice <= 0) {
        errorBox.textContent = "Введите корректную цену покупки.";
        errorBox.classList.remove("hidden");
        return;
      }

      errorBox.classList.add("hidden");
      saveBtn.disabled = true;
      saveBtn.textContent = "Сохраняю…";

      try {
        await apiPost("/api/stats/purchase", {
          telegram_id: state.telegramId,
          platform: product.platform,
          product_id: product.product_id,
          product_name: product.product_name,
          purchase_price: purchasePrice,
          purchase_date: dateInput.value,
          current_price: product.price,
          card_price: product.card_price,
          avg_price: product.avg_price,
          original_price: product.original_price,
        });

        await loadData();
        closePurchaseModal();
        // Re-render and go to purchases
        state.activeViewIndex = 2; // purchases
        renderRoot();
      } catch (error) {
        errorBox.textContent = `Не удалось сохранить покупку: ${error.message || error}`;
        errorBox.classList.remove("hidden");
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = "Сохранить покупку";
      }
    });
  }

  /* ── Event binding ── */

  function bindCommonEvents() {
    // Bottom nav
    document.querySelectorAll(".nav-item[data-nav]").forEach((btn) => {
      btn.addEventListener("click", () => setActiveView(btn.dataset.nav));
    });

    // Jump buttons inside views
    document.querySelectorAll("[data-view-jump]").forEach((btn) => {
      btn.addEventListener("click", () => setActiveView(btn.dataset.viewJump));
    });

    // Buy buttons
    document.querySelectorAll('[data-action="buy"]').forEach((btn) => {
      btn.addEventListener("click", () => openPurchaseModal(btn.dataset.platform, btn.dataset.productId));
    });
  }

  /* ── Data loading ── */

  async function loadData() {
    const [summary, productsResponse, activityResponse, purchasesResponse] = await Promise.all([
      apiGet(`/api/stats/summary?telegram_id=${state.telegramId}`),
      apiGet(`/api/stats/products?telegram_id=${state.telegramId}&limit=50`),
      apiGet(`/api/stats/activity?telegram_id=${state.telegramId}&days=30`),
      apiGet(`/api/stats/purchases?telegram_id=${state.telegramId}&limit=50`),
    ]);

    state.summary = summary;
    state.products = productsResponse.products || [];
    state.activity = activityResponse.activity || [];
    state.purchases = purchasesResponse.purchases || [];
  }

  function renderLoading() {
    $("root").innerHTML = `
      <div class="loader-card">
        <div class="spinner"></div>
        <div>Загружаю статистику…</div>
      </div>
    `;
  }

  function renderError(message, detail) {
    $("root").innerHTML = `
      <div class="error-card">
        <div class="section-title">Что-то пошло не так</div>
        <div>${escapeHtml(message)}</div>
        ${detail ? `<div class="error-detail">${escapeHtml(detail)}</div>` : ""}
      </div>
    `;
  }

  /* ── Main ── */

  async function main() {
    const telegramIdFromTG = getTelegramIdFromWebApp();
    const telegramIdFromQuery = getQueryParam("telegram_id");
    state.telegramId = telegramIdFromQuery ? Number(telegramIdFromQuery) : telegramIdFromTG;

    if (!state.telegramId || Number.isNaN(state.telegramId)) {
      $("subtitle").textContent = "Не удалось определить Telegram ID";
      renderError(
        "Откройте Mini App из Telegram или передайте telegram_id параметром.",
        "Пример для dev: /miniapp/?telegram_id=123456789",
      );
      return;
    }

    renderLoading();

    try {
      await loadData();
      renderRoot();
    } catch (error) {
      $("subtitle").textContent = "Ошибка загрузки";
      renderError(
        "Не удалось загрузить статистику. Проверьте доступность backend.",
        String(error && error.message ? error.message : error),
      );
    }
  }

  // Close modal on overlay click
  document.addEventListener("click", (event) => {
    const overlay = $("purchase-modal");
    if (!overlay.classList.contains("open")) return;
    if (event.target === overlay) closePurchaseModal();
  });

  main();
})();
