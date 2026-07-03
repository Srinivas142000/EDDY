/* EDDY shared JS — data loading, portfolio (localStorage), rendering utils */

const EDDY = (() => {
  const LS_KEY = "eddy_portfolio_v1";

  const PALETTE = [
    "#E3564A", "#4A9DE3", "#E3B341", "#3FB950", "#B36AE2",
    "#E38A41", "#41C8E3", "#D45CA2", "#9BE341", "#8B949E",
  ];

  // ---------- utils ----------
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  async function fetchJSON(path) {
    try {
      const res = await fetch(`${path}?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      return await res.json();
    } catch (e) {
      // Offline / not yet generated — callers render empty states
      try {
        const cached = await caches.match(path);
        if (cached) return await cached.json();
      } catch (_) { /* no SW yet */ }
      return null;
    }
  }

  function timeAgo(isoStr) {
    if (!isoStr) return "";
    const then = new Date(isoStr).getTime();
    const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
    if (mins < 1) return "now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.round(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.round(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(isoStr).toLocaleDateString();
  }

  const fmtMoney = (v) => `$${Number(v || 0).toFixed(2)}`;
  const fmtPct = (v) => `${v >= 0 ? "+" : ""}${Number(v || 0).toFixed(2)}%`;

  // Event-level confidence = its top industry's confidence
  const eventConfidence = (ev) =>
    ev.industries && ev.industries.length ? ev.industries[0].confidence : 0;
  const topSector = (ev) =>
    ev.industries && ev.industries.length ? ev.industries[0].sector : "—";

  // ---------- confidence visuals ----------
  function dots(conf) {
    const on = conf >= 75 ? 3 : conf >= 50 ? 2 : 1;
    let html = '<span class="dots" title="' + conf + '%">';
    for (let i = 0; i < 3; i++) html += `<i class="${i < on ? "on" : ""}"></i>`;
    return html + "</span>";
  }

  function confBar(conf) {
    return `<span class="conf-bar" title="${conf}%"><i style="width:${Math.max(2, Math.min(100, conf))}%"></i></span>`;
  }

  // ---------- portfolio (localStorage is the device's source of truth) ----------
  function loadPortfolio() {
    try {
      const p = JSON.parse(localStorage.getItem(LS_KEY));
      if (p && Array.isArray(p.holdings)) return p;
    } catch (_) { /* corrupted — reset */ }
    return { holdings: [] };
  }

  function savePortfolio(p) {
    localStorage.setItem(LS_KEY, JSON.stringify(p));
  }

  function addHolding(ticker, priceAtPurchase, shares) {
    const p = loadPortfolio();
    p.holdings.push({
      ticker: ticker.toUpperCase().trim(),
      name: ticker.toUpperCase().trim(),
      shares: Number(shares),
      price_at_purchase: Number(priceAtPurchase),
      current_price: null,
      last_price_update: null,
    });
    savePortfolio(p);
    return p;
  }

  function removeHolding(index) {
    const p = loadPortfolio();
    p.holdings.splice(index, 1);
    savePortfolio(p);
    return p;
  }

  // Merge repo-committed prices (refreshed by the cron job) into local holdings
  function mergePrices(local, repo) {
    if (!repo || !Array.isArray(repo.holdings)) return local;
    const prices = {};
    repo.holdings.forEach((h) => {
      if (h.current_price != null) {
        prices[h.ticker] = { price: h.current_price, at: h.last_price_update, name: h.name };
      }
    });
    local.holdings.forEach((h) => {
      const p = prices[h.ticker];
      if (p) {
        h.current_price = p.price;
        h.last_price_update = p.at;
        if (p.name) h.name = p.name;
      }
    });
    return local;
  }

  function computeTotals(p) {
    let invested = 0, value = 0;
    p.holdings.forEach((h) => {
      const cur = h.current_price != null ? h.current_price : h.price_at_purchase;
      h.current_value = +(h.shares * cur).toFixed(2);
      h.gain_loss_pct = h.price_at_purchase
        ? +(((cur - h.price_at_purchase) / h.price_at_purchase) * 100).toFixed(2)
        : 0;
      invested += h.shares * h.price_at_purchase;
      value += h.shares * cur;
    });
    p.total_invested = +invested.toFixed(2);
    p.total_current_value = +value.toFixed(2);
    p.total_gain_loss_pct = invested ? +(((value - invested) / invested) * 100).toFixed(2) : 0;
    return p;
  }

  function exportPortfolio() {
    const p = computeTotals(loadPortfolio());
    p.last_updated = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    const blob = new Blob([JSON.stringify(p, null, 2) + "\n"], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "portfolio.json";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // ---------- SVG donut / pie ----------
  function donutSVG(items, { size = 200, hole = 0.62, centerText = "" } = {}) {
    const total = items.reduce((s, it) => s + it.value, 0);
    const cx = size / 2, cy = size / 2, r = size / 2 - 4;
    let svg = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img">`;
    if (total <= 0 || !items.length) {
      svg += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#283039" stroke-width="${r * (1 - hole)}"/>`;
    } else if (items.length === 1) {
      svg += `<circle cx="${cx}" cy="${cy}" r="${r * (1 + hole) / 2}" fill="none" stroke="${items[0].color}" stroke-width="${r * (1 - hole)}" data-idx="0" class="slice"/>`;
    } else {
      let angle = -Math.PI / 2;
      items.forEach((it, idx) => {
        const frac = it.value / total;
        const a2 = angle + frac * 2 * Math.PI;
        const large = frac > 0.5 ? 1 : 0;
        const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
        const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
        const hr = r * hole;
        const hx1 = cx + hr * Math.cos(a2), hy1 = cy + hr * Math.sin(a2);
        const hx2 = cx + hr * Math.cos(angle), hy2 = cy + hr * Math.sin(angle);
        svg += `<path class="slice" data-idx="${idx}" d="M${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} L${hx1},${hy1} A${hr},${hr} 0 ${large} 0 ${hx2},${hy2} Z" fill="${it.color}" stroke="#0E1116" stroke-width="1.5" style="cursor:pointer"/>`;
        angle = a2;
      });
    }
    if (centerText) {
      svg += `<text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="central" fill="#E6EDF3" font-family="JetBrains Mono, monospace" font-weight="700" font-size="${size / 11}">${esc(centerText)}</text>`;
    }
    return svg + "</svg>";
  }

  // ---------- header + footer + SW ----------
  const DISCLAIMER =
    "EDDY is a signal tool only. All trades are executed manually. Past industry " +
    "correlations do not guarantee future price movements. Not financial advice. " +
    "Phase 3 accuracy validation required before real money.";

  function renderChrome({ back = false } = {}) {
    const header = document.querySelector("header.topbar");
    if (header) {
      header.innerHTML = back
        ? `<a class="icon-btn" href="index.html" aria-label="Back">←</a>
           <span class="wordmark">EDDY</span>
           <a class="icon-btn" href="index.html" aria-label="Home">⌂</a>`
        : `<a class="icon-btn" href="index.html" aria-label="Home">⌂</a>
           <span class="wordmark">EDDY</span>
           <button class="icon-btn" id="settingsBtn" aria-label="Settings">⚙</button>`;
      const btn = document.getElementById("settingsBtn");
      if (btn) btn.addEventListener("click", openSettings);
    }
    const footer = document.querySelector("footer.disclaimer");
    if (footer) footer.textContent = DISCLAIMER;
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
  }

  function openSettings() {
    let bd = document.getElementById("settingsModal");
    if (!bd) {
      bd = document.createElement("div");
      bd.id = "settingsModal";
      bd.className = "modal-backdrop";
      bd.innerHTML = `<div class="modal">
        <h3>Settings</h3>
        <p><strong>Data:</strong> events refresh every 30 minutes via GitHub Actions. Portfolio lives in this device's localStorage.</p>
        <p><strong>Notifications (Phase 4):</strong> subscribe to your ntfy.sh topic in the ntfy app to receive push signals.</p>
        <p class="muted" id="settingsStamp"></p>
        <button class="btn primary" id="settingsClose">Close</button>
      </div>`;
      document.body.appendChild(bd);
      bd.addEventListener("click", (e) => { if (e.target === bd) bd.classList.remove("show"); });
      bd.querySelector("#settingsClose").addEventListener("click", () => bd.classList.remove("show"));
    }
    bd.classList.add("show");
  }

  return {
    esc, fetchJSON, timeAgo, fmtMoney, fmtPct,
    eventConfidence, topSector, dots, confBar,
    loadPortfolio, savePortfolio, addHolding, removeHolding,
    mergePrices, computeTotals, exportPortfolio,
    donutSVG, PALETTE, renderChrome,
  };
})();
