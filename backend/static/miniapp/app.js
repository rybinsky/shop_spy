/*
 * ShopSpy Mini App
 * Показывает пользовательскую статистику (views/saved) по данным backend.
 */

(function () {
  "use strict";

  const DEFAULT_API_BASE = ""; // relative to current host
  const STORAGE_KEY_API_BASE = "shopspy_api_base";

  function $(id) {
    return document.getElementById(id);
  }

  function formatMoney(v) {
    if (v === null || v === undefined) return "—";
    const n = Number(v);
    if (Number.isNaN(n)) return "—";
    return `${Math.round(n).toLocaleString("ru")} ₽`;
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
      // Telegram Mini App
      if (window.Telegram && Telegram.WebApp) {
        Telegram.WebApp.ready();
        const user = Telegram.WebApp.initDataUnsafe?.user;
        if (user && user.id) return Number(user.id);
      }
    } catch (e) {
      // ignore
    }
    return null;
  }

  function getApiBase() {
    // Allow override for local dev / reverse proxy
    const fromQuery = getQueryParam("api");
    if (fromQuery) {
      localStorage.setItem(STORAGE_KEY_API_BASE, fromQuery);
      return fromQuery;
    }
    return localStorage.getItem(STORAGE_KEY_API_BASE) || DEFAULT_API_BASE;
  }

  async function apiGet(path) {
    const apiBase = getApiBase();
    const url = `${apiBase}${path}`;
    const r = await fetch(url, { headers: { "Content-Type": "application/json" } });
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      throw new Error(`HTTP ${r.status} for ${path}: ${text}`);
    }
    return await r.json();
  }

  function renderError(message, detail) {
    const root = $("root");
    root.innerHTML = `
      <div class="error">
        <b>Ошибка</b><br/>
        <div style="margin-top:6px;">${message}</div>
        ${detail ? `<div style="margin-top:8px;opacity:0.85;white-space:pre-wrap;">${detail}</div>` : ""}
      </div>
    `;
  }

  function render(summary, products, activity, telegramId) {
    const root = $("root");

    const best = summary.best_deal;
    const bestHtml = best
      ? `
        <div class="best">
          <div style="font-weight:800;margin-bottom:4px;">Лучшая находка</div>
          <div>${best.product_name || best.product_id} · ${platformLabel(best.platform).text}</div>
          <div style="margin-top:6px;">Экономия: <b style="color: var(--ok)">${formatMoney(best.saved_amount)}</b></div>
        </div>
      `
      : "";

    const listHtml = (products.products || [])
      .map((p) => {
        const pl = platformLabel(p.platform);
        const name = (p.product_name || p.product_id || "").replace(/</g, "&lt;");
        return `
          <div class="item">
            <div class="item-top">
              <div class="item-name">${name}</div>
              <div class="pill ${pl.cls}">${pl.text}</div>
            </div>
            <div class="item-meta">
              <span>Цена: <b>${formatMoney(p.price)}</b></span>
              <span>По карте: <b>${formatMoney(p.card_price)}</b></span>
              <span>Экономия: <b style="color: ${p.saved_amount > 0 ? "var(--ok)" : "rgba(234,234,242,0.92)"}">${formatMoney(p.saved_amount)}</b></span>
            </div>
            <div class="item-meta" style="opacity:0.9;">
              <span>Последний просмотр: <b>${p.last_view ? new Date(p.last_view).toLocaleString("ru") : "—"}</b></span>
            </div>
          </div>
        `;
      })
      .join("");

    const activityRows = (activity.activity || []).slice(0, 14);
    const activityHtml = activityRows.length
      ? `
        <div class="list">
          ${activityRows
            .map(
              (a) => `
            <div class="item">
              <div class="item-top">
                <div class="item-name">${a.date}</div>
                <div class="pill">Просмотры: ${a.views}</div>
              </div>
              <div class="item-meta">
                <span>Экономия: <b style="color:${a.saved > 0 ? "var(--ok)" : "rgba(234,234,242,0.92)"}">${formatMoney(a.saved)}</b></span>
              </div>
            </div>
          `,
            )
            .join("")}
        </div>
      `
      : `<div style="font-size:12px;color:var(--muted);">Пока нет активности.</div>`;

    root.innerHTML = `
      <div class="grid">
        <div class="card">
          <div class="card-title">Уникальных товаров</div>
          <div class="card-value">${summary.total_viewed}</div>
          <div class="card-hint">всего просмотрено</div>
        </div>
        <div class="card">
          <div class="card-title">Сэкономлено (всего)</div>
          <div class="card-value" style="color: var(--ok)">${formatMoney(summary.total_saved)}</div>
          <div class="card-hint">если цена ниже средней</div>
        </div>
        <div class="card">
          <div class="card-title">Просмотры (месяц)</div>
          <div class="card-value">${summary.monthly_views}</div>
        </div>
        <div class="card">
          <div class="card-title">Сэкономлено (месяц)</div>
          <div class="card-value" style="color: var(--ok)">${formatMoney(summary.monthly_saved)}</div>
        </div>
      </div>

      ${bestHtml}

      <div class="section">
        <h2>Последние товары</h2>
        ${listHtml || `<div style="font-size:12px;color:var(--muted);">Пока пусто. Открой несколько товаров в расширении.</div>`}
      </div>

      <div class="section">
        <h2>Активность (последние дни)</h2>
        ${activityHtml}
      </div>

      <div class="section" style="margin-top:18px;font-size:11px;color:rgba(234,234,242,0.55);">
        Telegram ID: <b style="color:rgba(234,234,242,0.85);">${telegramId}</b>
      </div>
    `;
  }

  async function main() {
    const subtitle = $("subtitle");

    const telegramIdFromTG = getTelegramIdFromWebApp();
    const telegramIdFromQuery = getQueryParam("telegram_id");
    const telegramId = telegramIdFromQuery
      ? Number(telegramIdFromQuery)
      : telegramIdFromTG;

    if (!telegramId || Number.isNaN(telegramId)) {
      subtitle.textContent = "Не удалось определить Telegram ID";
      renderError(
        "Откройте Mini App из Telegram или передайте telegram_id параметром.",
        "Пример для dev: /miniapp/?telegram_id=123456789",
      );
      return;
    }

    subtitle.textContent = `Telegram ID: ${telegramId}`;

    try {
      const [summary, products, activity] = await Promise.all([
        apiGet(`/api/stats/summary?telegram_id=${telegramId}`),
        apiGet(`/api/stats/products?telegram_id=${telegramId}&limit=50`),
        apiGet(`/api/stats/activity?telegram_id=${telegramId}&days=30`),
      ]);

      render(summary, products, activity, telegramId);
    } catch (e) {
      subtitle.textContent = "Ошибка загрузки";
      renderError(
        "Не удалось загрузить статистику. Проверьте, что backend доступен и CORS/прокси настроены.",
        String(e && e.message ? e.message : e),
      );
    }
  }

  main();
})();
