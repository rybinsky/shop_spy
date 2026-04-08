/**
 * ShopSpy Popup - Управление отслеживанием товаров
 */

const API_BASE = SHOPSPY_CONFIG.API_BASE;

// Состояние приложения
const state = {
  user: null,
  currentProduct: null,
  trackedProducts: [],
  stats: null,
  isLoading: true,
};

// Ключи для кэша
const CACHE_KEY = "shopspy_cache";
const CACHE_TTL = 5 * 60 * 1000; // 5 минут

// DOM элементы
const elements = {};

// Инициализация DOM элементов
function initElements() {
  elements.loader = document.getElementById("loader");
  elements.authSection = document.getElementById("auth-section");
  elements.userSection = document.getElementById("user-section");
  elements.userAvatar = document.getElementById("user-avatar");
  elements.userName = document.getElementById("user-name");
  elements.logoutBtn = document.getElementById("logout-btn");
  elements.loginBtn = document.getElementById("login-btn");
  elements.productSection = document.getElementById("product-section");
  elements.productPlatform = document.getElementById("product-platform");
  elements.productName = document.getElementById("product-name");
  elements.productPrice = document.getElementById("product-price");
  elements.productPriceOld = document.getElementById("product-price-old");
  elements.trackBtn = document.getElementById("track-btn");
  elements.trackBtnIcon = document.getElementById("track-btn-icon");
  elements.trackBtnText = document.getElementById("track-btn-text");
  elements.notMarketplaceSection = document.getElementById(
    "not-marketplace-section",
  );
  elements.trackedSection = document.getElementById("tracked-section");
  elements.trackedList = document.getElementById("tracked-list");
  elements.trackedEmpty = document.getElementById("tracked-empty");
  elements.errorContainer = document.getElementById("error-container");
  elements.errorMsg = document.getElementById("error-msg");
  elements.statsSection = document.getElementById("stats-section");
  elements.statViewed = document.getElementById("stat-viewed");
  elements.statTracked = document.getElementById("stat-tracked");
  elements.statSaved = document.getElementById("stat-saved");
  elements.bestDealSection = document.getElementById("best-deal-section");
  elements.bestDealName = document.getElementById("best-deal-name");
  elements.bestDealSaved = document.getElementById("best-deal-saved");
  elements.miniappLink = document.getElementById("miniapp-link");
}

// Показать/скрыть элемент
function show(el) {
  if (el) el.classList.remove("hidden");
}

function hide(el) {
  if (el) el.classList.add("hidden");
}

// Показать ошибку
function showError(message) {
  if (elements.errorMsg) {
    elements.errorMsg.textContent = message;
    show(elements.errorContainer);
    setTimeout(() => hide(elements.errorContainer), 5000);
  }
}

// Загрузка пользователя из хранилища
function loadUser() {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      ["telegram_id", "telegram_username", "telegram_photo"],
      (result) => {
        if (result.telegram_id) {
          resolve({
            id: result.telegram_id,
            username: result.telegram_username || "User",
            photo: result.telegram_photo || "",
          });
        } else {
          resolve(null);
        }
      },
    );
  });
}

// Загрузка кэша товаров
function loadTrackedCache() {
  return new Promise((resolve) => {
    chrome.storage.local.get([CACHE_KEY], (result) => {
      const cache = result[CACHE_KEY];
      if (
        cache &&
        cache.timestamp &&
        Date.now() - cache.timestamp < CACHE_TTL
      ) {
        resolve(cache.products || []);
      } else {
        resolve(null);
      }
    });
  });
}

// Сохранение кэша товаров
function saveTrackedCache(products) {
  return new Promise((resolve) => {
    chrome.storage.local.set(
      {
        [CACHE_KEY]: {
          products: products,
          timestamp: Date.now(),
        },
      },
      resolve,
    );
  });
}

// Сохранение пользователя в хранилище
function saveUser(user) {
  return new Promise((resolve) => {
    chrome.storage.local.set(
      {
        telegram_id: user.id,
        telegram_username: user.username,
        telegram_photo: user.photo,
      },
      resolve,
    );
  });
}

// Удаление пользователя из хранилища
function clearUser() {
  return new Promise((resolve) => {
    chrome.storage.local.remove(
      ["telegram_id", "telegram_username", "telegram_photo"],
      resolve,
    );
  });
}

// Определение текущего товара из URL
function getCurrentProduct() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      if (!tabs || !tabs[0]) {
        resolve(null);
        return;
      }

      const tab = tabs[0];
      const url = tab.url || "";

      // Wildberries паттерны
      const wbPatterns = [
        /wildberries\.ru\/catalog\/(\d+)\/detail\.aspx/i,
        /wildberries\.ru\/catalog\/(\d+)/i,
        /www\.wildberries\.ru\/catalog\/(\d+)/i,
      ];

      // Ozon паттерны
      const ozonPatterns = [
        /ozon\.ru\/product\/[^\/]*-(\d+)\/?/i,
        /ozon\.ru\/context\/detail\/id\/(\d+)/i,
        /www\.ozon\.ru\/product\/[^\/]*-(\d+)\/?/i,
      ];

      // Проверка WB
      for (const pattern of wbPatterns) {
        const match = url.match(pattern);
        if (match) {
          const productId = match[1];
          const product = await fetchProductInfo("wb", productId, url);
          resolve(product);
          return;
        }
      }

      // Проверка Ozon
      for (const pattern of ozonPatterns) {
        const match = url.match(pattern);
        if (match) {
          const productId = match[1];
          const product = await fetchProductInfo("ozon", productId, url);
          resolve(product);
          return;
        }
      }

      resolve(null);
    });
  });
}

// Получение информации о товаре из API
async function fetchProductInfo(platform, productId, url) {
  try {
    const response = await fetch(
      `${API_BASE}/api/price/history?platform=${platform}&product_id=${productId}`,
    );
    const data = await response.json();

    if (data.history && data.history.length > 0) {
      const latest = data.history[data.history.length - 1];
      return {
        platform: platform,
        productId: productId,
        name: latest.product_name || `Товар ${productId}`,
        price: latest.price,
        originalPrice: latest.original_price,
        url: url,
      };
    }

    return {
      platform: platform,
      productId: productId,
      name: `Товар ${productId}`,
      price: null,
      originalPrice: null,
      url: url,
    };
  } catch (e) {
    console.error("Error fetching product info:", e);
    return {
      platform: platform,
      productId: productId,
      name: `Товар ${productId}`,
      price: null,
      originalPrice: null,
      url: url,
    };
  }
}

// Загрузка отслеживаемых товаров
async function loadTrackedProducts(chatId) {
  try {
    const response = await fetch(`${API_BASE}/api/alerts?chat_id=${chatId}`);
    const data = await response.json();
    return data.alerts || [];
  } catch (e) {
    console.error("Error loading tracked products:", e);
    return [];
  }
}

// Загрузка статистики пользователя
async function loadUserStats(telegramId) {
  try {
    const response = await fetch(
      `${API_BASE}/api/stats/summary?telegram_id=${telegramId}`,
    );
    const data = await response.json();
    return data;
  } catch (e) {
    console.error("Error loading user stats:", e);
    return null;
  }
}

// Рендер статистики
function renderStats(stats) {
  if (!stats || !elements.statsSection) return;

  elements.statViewed.textContent = stats.total_viewed || 0;
  elements.statTracked.textContent = state.trackedProducts.length || 0;
  elements.statSaved.textContent = stats.total_saved
    ? stats.total_saved.toLocaleString("ru")
    : "0";

  if (stats.best_deal && stats.best_deal.saved_amount > 0) {
    elements.bestDealName.textContent = stats.best_deal.product_name || "Товар";
    elements.bestDealSaved.textContent = `Сэкономлено: ${stats.best_deal.saved_amount.toLocaleString("ru")} ₽`;
    show(elements.bestDealSection);
  } else {
    hide(elements.bestDealSection);
  }

  show(elements.statsSection);
}

// Добавление товара в отслеживание
async function trackProduct() {
  if (!state.user || !state.currentProduct) return;

  const product = state.currentProduct;

  try {
    elements.trackBtn.disabled = true;
    elements.trackBtnText.textContent = "Добавление...";

    const response = await fetch(`${API_BASE}/api/alerts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: state.user.id,
        platform: product.platform,
        product_id: product.productId,
        product_name: product.name,
        url: product.url,
      }),
    });

    const data = await response.json();

    if (data.status === "ok") {
      state.trackedProducts.push({
        platform: product.platform,
        product_id: product.productId,
        product_name: product.name,
        last_price: product.price,
      });
      renderUI();
    } else {
      showError(data.message || "Ошибка при добавлении");
    }
  } catch (e) {
    console.error("Error tracking product:", e);
    showError("Ошибка соединения");
  } finally {
    elements.trackBtn.disabled = false;
  }
}

// Удаление товара из отслеживания
async function untrackProduct(platform, productId) {
  if (!state.user) return;

  try {
    const response = await fetch(
      `${API_BASE}/api/alerts?chat_id=${state.user.id}&platform=${platform}&product_id=${productId}`,
      { method: "DELETE" },
    );

    const data = await response.json();

    if (data.status === "ok") {
      state.trackedProducts = state.trackedProducts.filter(
        (p) => !(p.platform === platform && p.product_id === productId),
      );
      renderUI();
    }
  } catch (e) {
    console.error("Error untracking product:", e);
    showError("Ошибка при удалении");
  }
}

// Проверка, отслеживается ли товар
function isProductTracked(platform, productId) {
  return state.trackedProducts.some(
    (p) => p.platform === platform && p.product_id === productId,
  );
}

// Рендер UI
function renderUI() {
  hide(elements.loader);

  if (state.user) {
    hide(elements.authSection);
    show(elements.userSection);

    if (state.user.photo) {
      elements.userAvatar.src = state.user.photo;
    } else {
      elements.userAvatar.src =
        'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="50" fill="%23e94560"/><text y="60" x="50" text-anchor="middle" font-size="40" fill="white">?</text></svg>';
    }
    elements.userName.textContent = state.user.username;
  } else {
    hide(elements.userSection);
    show(elements.authSection);
  }

  if (state.user && state.currentProduct) {
    hide(elements.notMarketplaceSection);
    show(elements.productSection);

    const product = state.currentProduct;
    elements.productPlatform.textContent =
      product.platform === "wb" ? "Wildberries" : "Ozon";
    elements.productPlatform.className = "product-platform " + product.platform;
    elements.productName.textContent = product.name;
    elements.productPrice.textContent = product.price
      ? product.price.toLocaleString("ru")
      : "—";

    if (product.originalPrice && product.originalPrice > product.price) {
      elements.productPriceOld.textContent =
        product.originalPrice.toLocaleString("ru") + " ₽";
      show(elements.productPriceOld);
    } else {
      hide(elements.productPriceOld);
    }

    const isTracked = isProductTracked(product.platform, product.productId);
    if (isTracked) {
      elements.trackBtn.className = "btn btn-tracked";
      elements.trackBtnIcon.textContent = "✓";
      elements.trackBtnText.textContent = "Отслеживается";
    } else {
      elements.trackBtn.className = "btn btn-primary";
      elements.trackBtnIcon.textContent = "👁️";
      elements.trackBtnText.textContent = "Отслеживать";
    }
  } else if (state.user) {
    hide(elements.productSection);
    show(elements.notMarketplaceSection);
  } else {
    hide(elements.productSection);
    hide(elements.notMarketplaceSection);
  }

  if (state.user) {
    show(elements.trackedSection);
    renderTrackedProducts();
  } else {
    hide(elements.trackedSection);
  }

  // Статистика показывается только для авторизованных пользователей
  if (state.user && state.stats) {
    renderStats(state.stats);
  } else {
    hide(elements.statsSection);
  }
}

// Рендер списка отслеживаемых товаров
function renderTrackedProducts() {
  if (state.trackedProducts.length === 0) {
    hide(elements.trackedList);
    show(elements.trackedEmpty);
    return;
  }

  hide(elements.trackedEmpty);
  show(elements.trackedList);

  let html = "";
  for (const product of state.trackedProducts) {
    const platformIcon = product.platform === "wb" ? "🟣" : "🔵";
    const priceText = product.last_price
      ? product.last_price.toLocaleString("ru") + " ₽"
      : "—";
    const name = product.product_name || `Товар ${product.product_id}`;
    const shortName = name.length > 35 ? name.substring(0, 35) + "..." : name;

    html += `<div class="tracked-item">`;
    html += `<div class="tracked-item-platform ${product.platform}">${platformIcon}</div>`;
    html += `<div class="tracked-item-info">`;
    html += `<div class="tracked-item-name">${escapeHtml(shortName)}</div>`;
    html += `<div class="tracked-item-price">${priceText}</div>`;
    html += `</div>`;
    html += `<button class="tracked-item-delete" data-platform="${product.platform}" data-id="${product.product_id}">×</button>`;
    html += `</div>`;
  }

  elements.trackedList.innerHTML = html;

  const deleteButtons = elements.trackedList.querySelectorAll(
    ".tracked-item-delete",
  );
  deleteButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const platform = btn.dataset.platform;
      const productId = btn.dataset.id;
      untrackProduct(platform, productId);
    });
  });
}

// Экранирование HTML
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Показать модальное окно для ввода Chat ID
function showChatIdModal() {
  const chatId = prompt(
    "Введите ваш Telegram Chat ID:\n\n" +
      "1. Откройте бота @shopspy_bot в Telegram\n" +
      "2. Отправьте команду /start\n" +
      "3. Бот пришлёт ваш Chat ID\n\n" +
      "Введите полученное число:",
  );

  if (chatId) {
    const id = parseInt(chatId.trim(), 10);
    if (isNaN(id) || id <= 0) {
      showError("Неверный формат Chat ID. Введите число.");
      return;
    }

    const user = {
      id: id,
      username: `User ${id}`,
      photo: "",
    };

    saveUser(user);
    state.user = user;

    // Проверяем пользователя на сервере
    verifyUser(id);
  }
}

// Проверка пользователя на сервере
async function verifyUser(telegramId) {
  try {
    const response = await fetch(
      `${API_BASE}/api/telegram/status?chat_id=${telegramId}`,
    );
    const data = await response.json();

    if (data.linked) {
      state.trackedProducts = await loadTrackedProducts(telegramId);
      renderUI();
    } else {
      // Пользователь ещё не писал боту
      showError("Сначала напишите /start боту @shopspy_bot в Telegram!");
    }
  } catch (e) {
    console.error("Error verifying user:", e);
    // Всё равно показываем UI, возможно сервер недоступен
    renderUI();
  }
}

// Выход
async function logout() {
  await clearUser();
  state.user = null;
  state.trackedProducts = [];
  renderUI();
}

// Предзагрузка для "пробуждения" сервера
let isServerWarmingUp = false;

async function warmupServer() {
  if (isServerWarmingUp) return;

  isServerWarmingUp = true;

  // Показываем пользователю что сервер просыпается
  const loader = document.getElementById("loader");
  if (loader) {
    loader.innerHTML = `
      <div class="spinner"></div>
      <span>Пробуждение сервера (до 30 сек)...</span>
    `;
  }

  try {
    // Быстрый ping для пробуждения сервера с Render.com
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    await fetch(`${API_BASE}/health`, {
      method: "HEAD",
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
  } catch (e) {
    // Игнорируем ошибки
  } finally {
    isServerWarmingUp = false;
  }
}

// Инициализация
async function init() {
  initElements();

  // Запускаем warmup сразу для пробуждения сервера
  warmupServer();

  state.user = await loadUser();

  // Пытаемся загрузить кэш для мгновенного отображения
  if (state.user) {
    const cachedProducts = await loadTrackedCache();
    if (cachedProducts && cachedProducts.length > 0) {
      state.trackedProducts = cachedProducts;
      // Скрываем loader и показываем кэшированные данные сразу
      hide(elements.loader);
      renderUI();
    }
  }

  // Обновляем текст загрузки
  const loader = document.getElementById("loader");
  if (loader && state.trackedProducts.length === 0) {
    loader.innerHTML = `
      <div class="spinner"></div>
      <span>Загрузка данных...</span>
    `;
  }

  // Параллельные запросы для ускорения загрузки
  const promises = [];
  let productIndex = 0;
  let statsIndex = -1;

  if (state.user) {
    promises.push(loadTrackedProducts(state.user.id));
    productIndex = 1; // getCurrentProduct будет вторым
    promises.push(loadUserStats(state.user.id));
    statsIndex = 2;
  }

  promises.push(getCurrentProduct());

  const results = await Promise.all(promises);

  // Распределяем результаты по индексам
  if (state.user) {
    state.trackedProducts = results[0] || [];
    // Сохраняем в кэш
    saveTrackedCache(state.trackedProducts);
    state.currentProduct = results[productIndex];
    if (statsIndex >= 0) {
      state.stats = results[statsIndex];
    }
  } else {
    state.currentProduct = results[0];
  }

  renderUI();

  if (elements.loginBtn) {
    elements.loginBtn.addEventListener("click", showChatIdModal);
  }
  if (elements.logoutBtn) {
    elements.logoutBtn.addEventListener("click", logout);
  }
  if (elements.trackBtn) {
    elements.trackBtn.addEventListener("click", trackProduct);
  }

  // Set dashboard link from config
  const dashLink = document.getElementById("dashboard-link");
  if (dashLink) {
    dashLink.href = API_BASE;
  }

  // Set miniapp link
  if (elements.miniappLink) {
    elements.miniappLink.href = `${API_BASE}/miniapp/`;
  }
}

document.addEventListener("DOMContentLoaded", init);
