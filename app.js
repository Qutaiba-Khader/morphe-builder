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
    for (const t of document.querySelectorAll(".tab")) {
      t.classList.toggle("is-active", t === tab);
      t.setAttribute("aria-selected", String(t === tab));
    }
    for (const p of document.querySelectorAll(".panel")) p.classList.toggle("is-active", p.id === tab.dataset.tab);
    if (tab.dataset.tab === "catalog") loadCatalog();
  });
}

/* ----------------------------------------------------------- downloads */

const historyCache = new Map();

function downloadButton(f) {
  const label = f.arch === "all" ? "Download" : `Download ${f.arch}`;
  return el("a", { class: "dl", href: f.url, rel: "noopener", title: f.sha256 ? `sha256 ${f.sha256}` : "" },
    el("span", { text: label }),
    el("small", { text: fmtSize(f.size) }));
}

function obtainiumButton(href, note) {
  return el("a", {
    class: "dl alt", href, rel: "noopener",
    title: "Adds this app to Obtainium, which then checks for updates by itself",
  }, el("span", { text: "Add to Obtainium" }), el("small", { text: note }));
}

function appCard(app, obtainium) {
  const card = el("article", { class: "card" });
  const actions = el("div", { class: "actions" }, app.files.map(downloadButton));

  const obt = obtainium?.entries.get(app.id);
  const clash = obtainium?.conflicts.get(app.id);
  let clashNote = null;
  if (obt && (obt.variants || []).length) {
    // one installable per phone: every architecture is offered on its own
    actions.append(obtainiumButton(obt.add_url, obt.arch));
    for (const v of obt.variants) actions.append(obtainiumButton(v.add_url, v.arch));
  } else if (obt) {
    actions.append(obtainiumButton(obt.add_url, "auto-updates"));
  } else if (clash) {
    const other = clash.shares_with_name || clash.shares_with;
    clashNote = el("p", { class: "warn-note",
      text: `Same package as ${other} (${clash.package}). Installing this one replaces it, so Obtainium tracks only one of the two.` });
  }

  const btn = el("button", { class: "more", type: "button", "aria-expanded": "false", text: "All versions" });
  const box = el("div", { class: "history", hidden: "" });
  btn.addEventListener("click", async () => {
    if (!box.hasAttribute("hidden")) {
      box.setAttribute("hidden", "");
      btn.textContent = "All versions";
      btn.setAttribute("aria-expanded", "false");
      return;
    }
    btn.disabled = true;
    try {
      if (!historyCache.has(app.id)) historyCache.set(app.id, await getJSON(`api/apps/${app.id}.json`));
      const data = historyCache.get(app.id);
      box.replaceChildren(...[
        app.package ? el("p", { class: "pkg", text: `Package ${app.package}` }) : null,
        el("ol", {}, data.builds.map((b) =>
          el("li", {},
            el("span", { class: "hv", text: b.version }),
            el("span", { class: "muted", text: fmtDate(b.published) }),
            b.files.map((f) => el("a", { href: f.url, rel: "noopener", text: `${f.arch === "all" ? "APK" : f.arch}, ${fmtSize(f.size)}` })))))
      ].filter(Boolean));
      box.removeAttribute("hidden");
      btn.textContent = `Hide versions (${data.builds.length})`;
      btn.setAttribute("aria-expanded", "true");
    } catch (err) {
      box.replaceChildren(el("p", { class: "err", text: String(err.message || err) }));
      box.removeAttribute("hidden");
    } finally {
      btn.disabled = false;
    }
  });

  // DOM append() would print a null as the text "null", so drop the missing parts
  card.append(...[
    el("div", { class: "mark", "aria-hidden": "true", text: (app.name || "?").trim().charAt(0).toUpperCase() }),
    el("div", { class: "info" },
      el("h2", {}, el("span", { text: app.name })),
      el("p", { class: "facts" },
        el("span", { class: "ver", text: app.version }),
        el("span", { text: `Built ${fmtDate(app.published)}`, title: app.tag || "" }))),
    actions, btn, clashNote, box,
  ].filter(Boolean));
  return card;
}

async function loadBuilds() {
  const host = $("#apps");
  const loading = $(".loading", host);
  try {
    const [data, obtainiumData] = await Promise.all([
      getJSON("api/latest.json"),
      getJSON("api/obtainium.json").catch(() => null),
    ]);
    const obtainium = obtainiumData ? {
      entries: new Map((obtainiumData.apps || []).map((a) => [a.app, a])),
      conflicts: new Map((obtainiumData.conflicts || []).map((c) => [c.app, c])),
    } : null;
    if (obtainiumData?.add_all_url && (obtainiumData.apps || []).length) {
      const all = $("#obtainium-all");
      if (all) { all.href = obtainiumData.add_all_url; all.hidden = false; }
    }

    const apps = Object.values(data.apps || {}).sort((a, b) => a.name.localeCompare(b.name));
    for (const channel of document.querySelectorAll(".channel")) {
      const pre = channel.dataset.channel === "pre";
      const mine = apps.filter((a) => Boolean(a.prerelease) === pre);
      $(".list", channel).replaceChildren(...mine.map((a) => appCard(a, obtainium)));
      channel.hidden = mine.length === 0;
    }
    if (!apps.length) {
      loading.textContent = "No builds yet. The first ones appear here after the next CI run.";
    } else {
      loading.remove();
      const newest = apps.map((a) => a.published).filter(Boolean).sort().at(-1);
      $("#last-build").replaceChildren(
        "Last build ", el("b", { text: fmtDate(newest) }), `. ${apps.length} app${apps.length === 1 ? "" : "s"}, checked for updates every day.`);
    }
    $("#generated").textContent = data.generated ? "Updated " + fmtDate(data.generated) : "";
  } catch (err) {
    const msg = loading || host.appendChild(el("p"));
    msg.className = "err";
    msg.textContent = "Could not load the builds: " + (err.message || err) + ". Reload the page to try again.";
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
  det.append(el("div", { class: "table-scroll" }, table));
  if ((src.universal_patches || []).length) {
    det.append(el("p", { class: "muted", text: "Universal patches: " + src.universal_patches.join(", ") }));
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
      host.replaceChildren(el("p", { class: "muted", text: "The catalog has not been generated yet. Run the Catalog workflow." }));
      return;
    }
    host.replaceChildren(
      el("p", { class: "muted",
        text: `${sources.length} patch sources can patch ${Object.keys(cat.packages || {}).length} apps. Updated ${fmtDate(cat.generated)}.` }),
      ...sources.map(([k, v]) => sourceBlock(k, v)));

    $("#catalog-search").addEventListener("input", (ev) => {
      const q = ev.target.value.trim().toLowerCase();
      for (const det of host.querySelectorAll("details.src")) {
        det.hidden = q !== "" && !det.dataset.search.includes(q);
      }
    });
  } catch (err) {
    catalogLoaded = false;
    host.replaceChildren(el("p", { class: "err", text: "Could not load the catalog: " + (err.message || err) }));
  }
}

/* ----------------------------------------------------------------- api */

async function loadApi() {
  const base = location.href.replace(/[#?].*$/, "").replace(/[^/]*$/, "");
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
    $("#api-body").replaceChildren(el("p", { class: "err", text: "The API index has not been generated yet." }));
  }
}

loadBuilds();
loadApi();
