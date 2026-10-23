"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  // DOM append() would print a null as the text "null", so drop the missing parts
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false && kid !== "") node.append(kid);
  return node;
};
const svg = (d) => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", d);
  s.append(p);
  return s;
};
const ICON = {
  folder: "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  check: "M5 12l4 4L19 6",
  star: "M12 3l2.7 5.6 6.2.9-4.5 4.4 1.1 6.1L12 17.1 6.5 20l1.1-6.1L3.1 9.5l6.2-.9z",
  plus: "M12 5v14M5 12h14",
  copy: "M9 9h11v11H9zM5 15V4h11",
  link: "M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1",
};

const fmtSize = (b) => (!b ? "" : b >= 1e9 ? (b / 1e9).toFixed(2) + " GB" : (b / 1e6).toFixed(1) + " MB");
const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
};
const fmtAbs = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};
const getJSON = async (path) => {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
};
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private window */ } },
};

/* --------------------------------------------------------------- theme */

(() => {
  const root = document.documentElement;
  if (!store.get("mb-theme") && window.matchMedia?.("(prefers-color-scheme: light)").matches) root.dataset.theme = "light";
  $("#theme")?.addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
    store.set("mb-theme", root.dataset.theme);
  });
})();

/* ---------------------------------------------------------------- tabs */

const PLACEHOLDER = { "apps-panel": "Search apps…", community: "Search 1,000+ patchable apps…", catalog: "Search apps…", install: "Search apps…", api: "Search apps…" };

function showTab(id) {
  const tab = $(`.tab[data-tab="${id}"]`);
  if (!tab) return;
  for (const t of $$(".tab")) {
    t.classList.toggle("is-active", t === tab);
    t.setAttribute("aria-selected", String(t === tab));
  }
  for (const p of $$(".panel")) p.classList.toggle("is-active", p.id === id);
  $("#search").placeholder = PLACEHOLDER[id] || "Search…";
  if (id === "catalog") loadCatalog();
  if (id === "community") renderCommunity();
  applySearch();
}
for (const tab of $$(".tab")) {
  tab.addEventListener("click", () => {
    showTab(tab.dataset.tab);
    history.replaceState(null, "", tab.dataset.tab === "apps-panel" ? location.pathname : `#${tab.dataset.tab}`);
  });
}

/* --------------------------------------------------------------- search */

const query = () => ($("#search")?.value || "").trim().toLowerCase();
function applySearch() {
  const q = query();
  const active = $(".panel.is-active")?.id;
  if (active === "community") { communityShown = PAGE; renderCommunity(); return; }
  for (const card of $$("#apps .card")) card.hidden = q !== "" && !card.dataset.search.includes(q);
  applyFilter();
}
$("#search")?.addEventListener("input", applySearch);

/* ----------------------------------------------------------- downloads */

const historyCache = new Map();

function downloadButton(f) {
  const label = f.arch === "all" ? "Download" : `Download ${f.arch}`;
  return el("a", { class: "dl", href: f.url, rel: "noopener", title: f.sha256 ? `sha256 ${f.sha256}` : "" },
    el("span", { text: label }),
    el("small", { text: fmtSize(f.size) }));
}

// "Patches 1.45.0-dev.20": the patch bundle(s) this build was made with
const patchesText = (b) => {
  const v = (b.patches || []).map((p) => p.version).filter(Boolean);
  return v.length ? `Patches ${v.join(" + ")}` : "";
};
const toolsTitle = (b) =>
  [...(b.patches || []).map((p) => p.file), b.cli ? `CLI ${b.cli.file}` : ""].filter(Boolean).join("\n");

function obtainiumButton(href, note) {
  return el("a", {
    class: "dl alt", href, rel: "noopener",
    title: "Adds this app to Obtainium, which then checks for updates by itself",
  }, el("span", { text: "Add to Obtainium" }), el("small", { text: note }));
}

function appIcon(src, name, cls = "icon") {
  const mark = () => el("div", { class: `${cls} mark`, "aria-hidden": "true", text: (name || "?").trim().charAt(0).toUpperCase() });
  if (!src) return mark();
  const img = el("img", { class: cls, src, alt: "", loading: "lazy", referrerpolicy: "no-referrer", width: "52", height: "52" });
  img.addEventListener("error", () => img.replaceWith(mark()), { once: true });
  return img;
}

function appCard(app, obtainium) {
  const pre = Boolean(app.prerelease);
  const card = el("article", { class: "card" });
  card.dataset.channel = pre ? "pre" : "stable";
  card.dataset.search = [app.name, app.package, app.source_package, ...(app.patch_sources || [])].filter(Boolean).join(" ").toLowerCase();

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
      box.replaceChildren(
        el("p", { class: "muted", text: app.package ? `Installs as ${app.package}` : "" }),
        el("ol", {}, data.builds.map((b) =>
          el("li", {},
            el("span", { class: "hv", text: b.version }),
            el("span", { class: "muted", text: fmtDate(b.published) }),
            patchesText(b) ? el("span", { class: "muted", text: patchesText(b), title: toolsTitle(b) }) : null,
            b.files.map((f) => el("a", { href: f.url, rel: "noopener", text: `${f.arch === "all" ? "APK" : f.arch}, ${fmtSize(f.size)}` }))))));
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
  actions.append(btn);

  const repos = (app.patch_sources || []).map((r) =>
    el("a", { class: "chip", href: `https://github.com/${r}`, rel: "noopener", title: "Patch source" }, svg(ICON.folder), el("span", { text: r })));

  card.append(...[
    el("div", { class: "card-head" },
      appIcon(app.icon, app.name),
      el("div", { class: "info" },
        el("h2", {}, el("span", { text: app.name })),
        el("p", { class: "pkg", text: app.package || app.source_package || "" })),
      el("span", { class: `chip badge-top ${pre ? "pre" : "ok"}`, text: pre ? "PRE-RELEASE" : "STABLE" })),
    el("p", { class: "facts" },
      el("span", { class: "chip ver", text: app.version }),
      el("span", { class: "chip ok" }, svg(ICON.check), el("span", { text: "BUILT" })),
      el("span", { text: `Built ${fmtDate(app.published)}`, title: app.tag || "" }),
      patchesText(app) ? el("span", { text: patchesText(app), title: toolsTitle(app) }) : null),
    repos.length ? el("div", { class: "repos" }, repos) : null,
    clashNote, actions, box].filter(Boolean));
  return card;
}

let activeFilter = "all";
function applyFilter() {
  for (const channel of $$(".channel")) {
    const visible = [...$$(".card", channel)].filter((c) => !c.hidden);
    channel.hidden = visible.length === 0 || (activeFilter !== "all" && channel.dataset.channel !== activeFilter);
  }
}
for (const b of $$(".filter[data-filter]")) {
  b.addEventListener("click", () => {
    activeFilter = b.dataset.filter;
    for (const x of $$(".filter[data-filter]")) x.classList.toggle("is-active", x === b);
    applyFilter();
  });
}

function nextRun() {
  // CI runs daily at 10:00 UTC (.github/workflows/ci.yml)
  const now = new Date();
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 10));
  if (next <= now) next.setUTCDate(next.getUTCDate() + 1);
  const mins = Math.round((next - now) / 60000);
  $("#stat-next").textContent = mins >= 60 ? `in ${Math.floor(mins / 60)}h ${mins % 60}m` : `in ${mins}m`;
  $("#stat-next-sub").textContent = `Daily at 10:00 UTC (${next.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })} here)`;
}

async function loadBuilds() {
  const host = $("#apps");
  const loading = $(".loading", host);
  nextRun();
  setInterval(nextRun, 60000);
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
    for (const channel of $$(".channel")) {
      const pre = channel.dataset.channel === "pre";
      const mine = apps.filter((a) => Boolean(a.prerelease) === pre);
      $(".list", channel).replaceChildren(...mine.map((a) => appCard(a, obtainium)));
      channel.hidden = mine.length === 0;
    }
    const nPre = apps.filter((a) => a.prerelease).length;
    $("#n-all").textContent = apps.length;
    $("#n-stable").textContent = apps.length - nPre;
    $("#n-pre").textContent = nPre;

    if (!apps.length) {
      loading.textContent = "No builds yet. The first ones appear here after the next CI run.";
    } else {
      loading.remove();
      const newest = apps.map((a) => a.published).filter(Boolean).sort().at(-1);
      const files = apps.flatMap((a) => a.files || []);
      const bytes = files.reduce((s, f) => s + (f.size || 0), 0);
      $("#last-build").replaceChildren(
        "Last build ", el("b", { text: fmtDate(newest) }), `. ${apps.length} app${apps.length === 1 ? "" : "s"}, checked for updates every day.`);
      $("#stat-last").textContent = fmtDate(newest).replace(/^./, (c) => c.toUpperCase());
      $("#stat-last-sub").textContent = fmtAbs(newest);
      $("#stat-apps").textContent = `${apps.length} app${apps.length === 1 ? "" : "s"}`;
      $("#stat-apps-sub").textContent = `${files.length} APK files, ${fmtSize(bytes)}`;
    }
    $("#generated").textContent = data.generated ? "Updated " + fmtDate(data.generated) : "";
    if (data.generated) {
      const pill = $("#status-pill");
      pill.textContent = `Site updated ${fmtDate(data.generated)}`;
      pill.className = "pill ok";
      pill.hidden = false;
    }
    applySearch();
  } catch (err) {
    const msg = loading || host.appendChild(el("p"));
    msg.className = "err";
    msg.textContent = "Could not load the builds: " + (err.message || err) + ". Reload the page to try again.";
  }
}

/* ------------------------------------------------------ patchable apps */

const PAGE = 60;
let community = null;
let communityShown = PAGE;
let cFilter = "all";
const communityCache = new Map();

async function loadCommunity() {
  if (community) return community;
  try {
    community = await getJSON("api/community/index.json");
  } catch {
    community = { apps: [], error: true };
  }
  const apps = community.apps || [];
  $("#stat-community").textContent = apps.length ? `${apps.filter((a) => a.package !== "__universal__").length.toLocaleString()} apps` : "–";
  $("#stat-community-sub").textContent = community.patch_sources ? `from ${community.patch_sources} community patch sources` : "from the Morphe community";
  $("#c-all").textContent = apps.length;
  $("#c-built").textContent = apps.filter((a) => (a.built_here || []).length).length;
  $("#c-many").textContent = apps.filter((a) => a.sources >= 3).length;
  return community;
}

for (const b of $$(".filter[data-cfilter]")) {
  b.addEventListener("click", () => {
    cFilter = b.dataset.cfilter;
    communityShown = PAGE;
    for (const x of $$(".filter[data-cfilter]")) x.classList.toggle("is-active", x === b);
    renderCommunity();
  });
}
$("#community-more")?.addEventListener("click", () => { communityShown += PAGE * 2; renderCommunity(); });

function configSnippet(app, src) {
  const table = (app.name || app.package).replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "") || "My-App";
  return [
    `[${table}]`,
    "enabled = true",
    `# apkmirror-dlurl = "https://www.apkmirror.com/apk/<vendor>/<app>/"   (best first source when the app is there)`,
    `gplay-dlurl = "https://play.google.com/store/apps/details?id=${app.package}"`,
    "",
    `[${table}.patches]`,
    `"${src.source === "gitlab" ? "gitlab" : "github"}:${src.repo.replace(/^gitlab:/, "")}" = []`,
  ].join("\n");
}

function sourceCard(app, src) {
  const versions = (src.versions || []).slice(0, 4).join(", ");
  const exp = (src.experimental || []).slice(0, 2).join(", ");
  const copy = el("button", { class: "btn ghost", type: "button" }, svg(ICON.copy), el("span", { text: "Copy for config.toml" }));
  const pre = el("pre", { hidden: "" }, el("code", { text: configSnippet(app, src) }));
  copy.addEventListener("click", async () => {
    pre.hidden = false;
    try {
      await navigator.clipboard.writeText(configSnippet(app, src));
      copy.lastChild.textContent = "Copied";
    } catch {
      copy.lastChild.textContent = "Select and copy below";
    }
  });
  const list = el("details", { class: "plist" },
    el("summary", { text: `The ${src.app_patches} patch${src.app_patches === 1 ? "" : "es"} for this app` }),
    el("ul", { class: "patch-list" }, (src.patch_list || []).map(([n, d]) => el("li", { title: d || "" }, el("b", { text: n }), d ? el("span", { text: d }) : null))));
  return el("div", { class: "src-card" },
    el("div", { class: "src-top" },
      el("h4", {}, el("a", { href: src.url, rel: "noopener", text: src.repo })),
      el("span", { class: "muted", text: src.author && src.author !== src.repo.split("/")[0] ? src.author : "" }),
      el("span", { class: "chip plain", title: "GitHub stars" }, svg(ICON.star), el("span", { text: String(src.stars || 0) })),
      src.updated ? el("span", { class: "muted", text: `updated ${fmtDate(src.updated)}` }) : null,
      src.used_here ? el("span", { class: "chip ok small", text: "USED HERE" }) : null,
      src.prerelease ? el("span", { class: "chip pre small", text: "PRE-RELEASE ONLY" }) : null),
    el("p", { class: "muted", text: [
      `${src.app_patches} patch${src.app_patches === 1 ? "" : "es"} for this app (${src.patches} in the bundle)`,
      versions ? `supports ${versions}` : app.package === "__universal__" ? "" : "any version",
      exp ? `experimental ${exp}` : "",
    ].filter(Boolean).join(" · ") }),
    el("div", { class: "src-actions" },
      el("a", { class: "btn primary", href: src.add, rel: "noopener", title: "Opens the Morphe app and adds this patch source" }, svg(ICON.plus), el("span", { text: "Add to the Morphe app" })),
      app.package === "__universal__" ? null : copy,
      el("a", { class: "btn ghost", href: src.url, rel: "noopener" }, svg(ICON.link), el("span", { text: "Source" }))),
    pre, list);
}

function communityRow(a) {
  const built = (a.built_here || []).length;
  const det = el("details", { class: "row" });
  det.append(el("summary", {},
    a.package === "__universal__" ? el("div", { class: "icon mark", "aria-hidden": "true", text: "★" }) : appIcon(a.icon, a.name),
    el("div", { class: "row-main" },
      el("h3", { text: a.name || a.package }),
      el("p", { class: "pkg", text: a.package === "__universal__" ? "patches that work on any app" : a.package })),
    el("div", { class: "row-side" },
      built ? el("span", { class: "chip ok small", text: "BUILT HERE" }) : null,
      el("span", { class: "count", text: `${a.sources} SOURCE${a.sources === 1 ? "" : "S"}` }))));
  const body = el("div", { class: "row-body" }, el("p", { class: "muted", text: "Loading…" }));
  det.append(body);
  det.addEventListener("toggle", async () => {
    if (!det.open || det.dataset.loaded) return;
    det.dataset.loaded = "1";
    try {
      if (!communityCache.has(a.file)) communityCache.set(a.file, await getJSON(a.file));
      const app = communityCache.get(a.file);
      body.replaceChildren(
        built ? el("p", { class: "note" }, "Built here as ", el("b", { text: a.built_here.join(", ") }), ". See the Apps tab.") : null,
        ...app.sources.map((s) => sourceCard(app, s)));
    } catch (err) {
      delete det.dataset.loaded;
      body.replaceChildren(el("p", { class: "err", text: "Could not load: " + (err.message || err) }));
    }
  });
  return det;
}

async function renderCommunity() {
  const host = $("#community-list");
  const data = await loadCommunity();
  if (data.error) {
    host.replaceChildren(el("p", { class: "muted", text: "The community list has not been generated yet. It arrives with the next Catalog run." }));
    return;
  }
  const q = query();
  let apps = data.apps || [];
  if (cFilter === "built") apps = apps.filter((a) => (a.built_here || []).length);
  if (cFilter === "many") apps = apps.filter((a) => a.sources >= 3);
  if (q) apps = apps.filter((a) => `${a.name} ${a.package} ${(a.top || []).join(" ")} ${a.category || ""}`.toLowerCase().includes(q));
  // most-covered first; the universal patches on top when nothing is searched
  apps = [...apps].sort((x, y) => (y.package === "__universal__") - (x.package === "__universal__") || y.sources - x.sources || x.name.localeCompare(y.name));
  host.replaceChildren(...(apps.length ? apps.slice(0, communityShown).map(communityRow) : [el("p", { class: "muted", text: "No app matches." })]));
  const more = $("#community-more");
  more.hidden = apps.length <= communityShown;
  more.textContent = `Show more (${apps.length - Math.min(apps.length, communityShown)} left)`;
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
  for (const node of $$(".api-base")) node.textContent = base;
  try {
    const idx = await getJSON("api/index.json");
    if (idx.signing_cert_sha256) {
      $("#signer").textContent = idx.signing_cert_sha256.match(/../g).join(":").toUpperCase();
      $("#signer-note").hidden = false;
    }
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
loadCommunity();
if (location.hash && $(`.tab[data-tab="${location.hash.slice(1)}"]`)) showTab(location.hash.slice(1));
