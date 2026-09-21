"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid) node.append(kid);
  return node;
};

const fmtSize = (b) => (!b ? "" : b >= 1e9 ? (b / 1e9).toFixed(2) + " GB" : (b / 1e6).toFixed(1) + " MB");

const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  const abs = d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return abs;
};

const getJSON = async (path) => {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
};

/* ---------------------------------------------------------------- tabs */

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    for (const t of document.querySelectorAll(".tab")) t.classList.toggle("is-active", t === tab);
    for (const p of document.querySelectorAll(".panel")) p.classList.toggle("is-active", p.id === tab.dataset.tab);
    if (tab.dataset.tab === "catalog") loadCatalog();
  });
}

/* -------------------------------------------------------------- builds */

const historyCache = new Map();

function fileRow(f) {
  const label = f.arch === "all" ? "Download" : `Download ${f.arch}`;
  return el("a", { class: "dl", href: f.url, rel: "noopener", title: f.sha256 ? `sha256 ${f.sha256}` : "" },
    el("span", { text: label }),
    el("small", { text: fmtSize(f.size) }));
}

function appCard(app, obtainium) {
  const card = el("div", { class: "card" });
  card.append(
    el("h2", {},
      el("span", { text: app.name }),
      el("span", { class: "chip", text: app.brand }),
      app.prerelease ? el("span", { class: "chip pre", text: "pre-release" }) : null),
    el("p", { class: "ver", text: "v" + app.version }),
    el("p", { class: "meta", text: `${fmtDate(app.published)} · ${app.tag}` }),
    el("div", { class: "files" }, app.files.map(fileRow)));

  const obt = obtainium?.entries.get(app.id);
  const clash = obtainium?.conflicts.get(app.id);
  const obtButton = (href, label, note) => el("a", {
    class: "dl alt", href, rel: "noopener",
    title: "Adds this app to Obtainium so it checks for updates by itself",
  }, el("span", { text: label }), el("small", { text: note }));
  if (obt && (obt.variants || []).length) {
    // one installable per phone: offer every architecture on its own
    card.append(obtButton(obt.add_url, "Add to Obtainium", obt.arch));
    for (const v of obt.variants) card.append(obtButton(v.add_url, "Add to Obtainium", v.arch));
  } else if (obt) {
    card.append(obtButton(obt.add_url, "Add to Obtainium", "auto-updates"));
  } else if (clash) {
    const other = clash.shares_with_name || clash.shares_with;
    card.append(el("p", { class: "meta warn-note" },
      el("span", { text: `Same package as ${other} (${clash.package}) — installing this one replaces it, so Obtainium tracks only one of the two.` })));
  }

  const btn = el("button", { class: "more", type: "button", text: "All versions" });
  const box = el("div", { class: "history", hidden: "" });
  btn.addEventListener("click", async () => {
    const open = box.hasAttribute("hidden");
    if (!open) { box.setAttribute("hidden", ""); btn.textContent = "All versions"; return; }
    btn.disabled = true;
    try {
      if (!historyCache.has(app.id)) historyCache.set(app.id, await getJSON(`api/apps/${app.id}.json`));
      const data = historyCache.get(app.id);
      box.replaceChildren(el("ol", {}, data.builds.map((b) =>
        el("li", {},
          el("span", { class: "hv", text: "v" + b.version }),
          el("span", { class: "muted", text: fmtDate(b.published) }),
          b.files.map((f) => el("a", { href: f.url, rel: "noopener", text: `${f.arch} · ${fmtSize(f.size)}` }))))));
      box.removeAttribute("hidden");
      btn.textContent = `Hide versions (${data.builds.length})`;
    } catch (err) {
      box.replaceChildren(el("p", { class: "err", text: String(err.message || err) }));
      box.removeAttribute("hidden");
    } finally {
      btn.disabled = false;
    }
  });

  card.append(btn, box);
  return card;
}

async function loadBuilds() {
  const host = $("#apps");
  try {
    const [data, obtainiumData] = await Promise.all([
      getJSON("api/latest.json"),
      getJSON("api/obtainium.json").catch(() => null),
    ]);
    const obtainium = obtainiumData ? {
      entries: new Map((obtainiumData.apps || []).map((a) => [a.app, a])),
      conflicts: new Map((obtainiumData.conflicts || []).map((c) => [c.app, c])),
    } : null;
    if (obtainiumData?.add_all_url) {
      const all = $("#obtainium-all");
      if (all) { all.href = obtainiumData.add_all_url; all.hidden = false; }
    }
    const apps = Object.values(data.apps || {}).sort((a, b) => a.name.localeCompare(b.name));
    if (!apps.length) {
      host.replaceChildren(el("p", { class: "muted", text: "No builds published yet — the first CI run will fill this in." }));
    } else {
      host.replaceChildren(...apps.map((a) => appCard(a, obtainium)));
    }
    $("#generated").textContent = data.generated ? "Updated " + fmtDate(data.generated) : "";
  } catch (err) {
    host.replaceChildren(el("p", { class: "err", text: "Could not load builds: " + (err.message || err) }));
  }
}

/* ------------------------------------------------------------- catalog */

let catalogLoaded = false;

function sourceBlock(key, src) {
  const packages = Object.entries(src.packages || {});
  const det = el("details", { class: "src" });
  det.append(el("summary", {},
    el("span", { text: key.replace(/^github:|^gitlab:/, "") }),
    el("span", { class: "chip", text: src.version || "?" }),
    el("span", { class: "chip", text: `${src.patch_count || 0} patches` }),
    el("span", { class: "chip", text: `${packages.length} apps` }),
    src.error ? el("span", { class: "err", text: src.error }) : null));

  const table = el("table", {},
    el("tr", {},
      el("th", { text: "Package" }),
      el("th", { text: "Versions" }),
      el("th", { text: "Patches", title: "recommended (on by default) of total" })));
  for (const [pkg, info] of packages) {
    const all = info.patches || [];
    const on = all.filter((p) => p.default).length;
    table.append(el("tr", {},
      el("td", {}, el("code", { text: pkg })),
      el("td", { class: "muted", text: (info.versions || []).slice(0, 3).join(", ") || "any" }),
      el("td", { text: `${on} of ${all.length}` })));
  }
  det.append(table);
  if ((src.universal_patches || []).length) {
    det.append(el("p", { class: "muted", text: "Universal: " + src.universal_patches.join(", ") }));
  }
  det.dataset.search = (key + " " + packages.map(([p]) => p).join(" ")).toLowerCase();
  return det;
}

async function loadCatalog() {
  if (catalogLoaded) return;
  catalogLoaded = true;
  const host = $("#catalog-body");
  try {
    const cat = await getJSON("api/catalog.json");
    const sources = Object.entries(cat.sources || {});
    if (!sources.length) {
      host.replaceChildren(el("p", { class: "muted", text: "Catalog not generated yet — run the Catalog workflow." }));
      return;
    }
    host.replaceChildren(
      el("p", { class: "muted", text: `${sources.length} sources · ${Object.keys(cat.packages || {}).length} apps · generated ${fmtDate(cat.generated)}` }),
      ...sources.map(([k, v]) => sourceBlock(k, v)));

    $("#catalog-search").addEventListener("input", (ev) => {
      const q = ev.target.value.trim().toLowerCase();
      for (const det of host.querySelectorAll("details.src")) {
        det.hidden = q !== "" && !det.dataset.search.includes(q);
      }
    });
  } catch (err) {
    catalogLoaded = false;
    host.replaceChildren(el("p", { class: "err", text: "Could not load catalog: " + (err.message || err) }));
  }
}

/* ----------------------------------------------------------------- api */

async function loadApi() {
  const base = location.href.replace(/[^/]*$/, "");
  for (const node of document.querySelectorAll(".api-base")) node.textContent = base;
  try {
    const idx = await getJSON("api/index.json");
    const rows = Object.entries(idx.endpoints || {}).map(([name, path]) =>
      el("div", { class: "ep" },
        el("b", { text: name }),
        path.includes("{")
          ? el("code", { text: base + path })
          : el("a", { href: path, text: base + path })));
    $("#api-body").replaceChildren(...rows);
  } catch {
    $("#api-body").replaceChildren(el("p", { class: "err", text: "API index not generated yet." }));
  }
}

loadBuilds();
loadApi();
