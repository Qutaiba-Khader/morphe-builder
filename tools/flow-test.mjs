// Flow test: drive the published page exactly as a visitor would, against the LIVE site.
// jsdom runs the real app.js; fetch hits the real Pages origin.
import { readFileSync } from "node:fs";
import { JSDOM, VirtualConsole } from "jsdom";

const BASE = "https://qutaiba-khader.github.io/morphe-builder/";
const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const html = await (await fetch(BASE)).text();
const appjs = await (await fetch(BASE + "app.js")).text();

const vc = new VirtualConsole();
const consoleErrors = [];
vc.on("jsdomError", (e) => consoleErrors.push(String(e.message)));
vc.on("error", (...a) => consoleErrors.push(a.join(" ")));

const dom = new JSDOM(html, { url: BASE, runScripts: "outside-only", virtualConsole: vc, pretendToBeVisual: true });
const { window } = dom;
window.fetch = (input, init) => fetch(new URL(input, BASE).href, init);

window.eval(appjs);
await sleep(2500);

const doc = window.document;
const $ = (s) => doc.querySelector(s);
const $$ = (s) => [...doc.querySelectorAll(s)];

// --- builds tab -------------------------------------------------------------
const index = await (await fetch(BASE + "api/index.json")).json();
const configNames = new Set(index.apps.map((a) => a.name));

const cards = $$("#apps .card");
check("builds: a card per app", cards.length === index.apps.length, `${cards.length} card(s)`);

const titleOf = (c) => c.querySelector("h2 span")?.textContent ?? "";
check("builds: names come from config.toml, capitalisation intact",
  cards.every((c) => configNames.has(titleOf(c))) && configNames.has("YouTube"),
  cards.map(titleOf).join(", "));

// use YouTube for the per-card assertions so they do not depend on sort order
const card = cards.find((c) => titleOf(c) === "YouTube") ?? cards[0];
check("builds: version shown", /^v\d/.test(card?.querySelector(".ver")?.textContent ?? ""), card?.querySelector(".ver")?.textContent);

const dl = card?.querySelector("a.dl");
check("builds: download link points at the release asset",
  !!dl && dl.href.includes("/releases/download/") && dl.href.endsWith(".apk"), dl?.href);
check("builds: download shows a size", /\d+(\.\d+)? MB/.test(dl?.querySelector("small")?.textContent ?? ""),
  dl?.querySelector("small")?.textContent);
check("builds: sha256 exposed on the link", (dl?.getAttribute("title") ?? "").startsWith("sha256 "),
  dl?.getAttribute("title")?.slice(0, 22));
check("builds: updated stamp in footer", ($("#generated")?.textContent ?? "").startsWith("Updated"),
  $("#generated")?.textContent);

// --- all versions -----------------------------------------------------------
const more = card?.querySelector("button.more");
check("history: button present and labelled", more?.textContent === "All versions", more?.textContent);
more?.click();
await sleep(1500);
const hist = card?.querySelector(".history");
const items = hist ? [...hist.querySelectorAll("ol li")] : [];
check("history: opens and lists versions", !hist?.hasAttribute("hidden") && items.length > 0, `${items.length} version(s)`);
check("history: each row links to a file", items.every((li) => li.querySelector("a[href*='/releases/download/']")));
check("history: button becomes a hide toggle", (more?.textContent ?? "").startsWith("Hide versions"), more?.textContent);
more?.click();
await sleep(200);
check("history: closes again", hist?.hasAttribute("hidden") && more?.textContent === "All versions");

// --- catalog tab ------------------------------------------------------------
const catalogTab = $$(".tab").find((t) => t.dataset.tab === "catalog");
catalogTab?.click();
await sleep(2500);
check("tabs: catalog panel becomes visible",
  $("#catalog")?.classList.contains("is-active") && !$("#builds")?.classList.contains("is-active"));
const sources = $$("#catalog-body details.src");
check("catalog: sources rendered", sources.length > 0, `${sources.length} source(s)`);
const morphe = sources.find((d) => d.querySelector("summary span")?.textContent === "MorpheApp/morphe-patches");
check("catalog: the Morphe source is listed", !!morphe);
check("catalog: packages table filled", (morphe?.querySelectorAll("table tr").length ?? 0) > 1,
  `${(morphe?.querySelectorAll("table tr").length ?? 1) - 1} package row(s)`);
check("catalog: youtube package present",
  [...(morphe?.querySelectorAll("td code") ?? [])].some((c) => c.textContent === "com.google.android.youtube"));

const search = $("#catalog-search");
search.value = "tiktok";
search.dispatchEvent(new window.Event("input"));
await sleep(100);
const visible = sources.filter((d) => !d.hidden);
check("catalog: search filters the list", visible.length > 0 && visible.length < sources.length,
  `${visible.length}/${sources.length} shown for "tiktok"`);
search.value = "";
search.dispatchEvent(new window.Event("input"));

// --- obtainium --------------------------------------------------------------
const obtBtn = card?.querySelector("a.dl.alt");
check("obtainium: add button on the card", obtBtn?.textContent.includes("Add to Obtainium"), obtBtn?.textContent);
check("obtainium: button targets the redirect service",
  (obtBtn?.href ?? "").startsWith("https://apps.obtainium.imranr.dev/redirect?r=obtainium%3A%2F%2Fapp%2F"));

const allLink = $("#obtainium-all");
check("obtainium: add-all link revealed",
  !allLink?.hidden && (allLink?.href ?? "").includes("obtainium%3A%2F%2Fapps%2F"));

const obt = await (await fetch(BASE + "api/obtainium.json")).json();
const clashes = obt.conflicts || [];
check("obtainium: every app is either addable or reported as a conflict",
  obt.apps.length + clashes.length === cards.length,
  `${obt.apps.length} addable + ${clashes.length} conflict(s) vs ${cards.length} card(s)`);

for (const c of clashes) {
  const owner = obt.apps.find((a) => a.app === c.shares_with);
  check(`obtainium/${c.app}: conflict points at an app that IS addable`,
    !!owner && owner.config.id === c.package, `${c.shares_with} -> ${owner?.config.id}`);
  const clashCard = cards.find((el) => titleOf(el) === (index.apps.find((a) => a.id === c.app)?.name));
  check(`obtainium/${c.app}: its card explains the clash instead of offering a button`,
    !clashCard?.querySelector("a.dl.alt") && /replaces it/.test(clashCard?.textContent ?? ""));
}

for (const entry of obt.apps) {
  const cfg = entry.config;
  const settings = JSON.parse(cfg.additionalSettings);
  check(`obtainium/${entry.app}: config is complete`,
    !!cfg.url && !!cfg.name && !!cfg.author && !!cfg.id, JSON.stringify({ id: cfg.id, author: cfg.author }));

  // Replay exactly what Obtainium's HTML source does:
  //   fetch the page -> keep links matching apkFilterRegEx -> take the LAST one
  //   -> run versionExtractionRegEx over the whole DECODED URL (not the filename)
  //      (lib/app_sources/html.dart; extractVersion in lib/services/version_service.dart
  //       throws NoVersionError -> "Could not determine release version" on no match)
  const page = await fetch(entry.source_url);
  const body = await page.text();
  const all = [...body.matchAll(/href="([^"]+)"/g)].map((x) => x[1]);
  const links = all.filter((u) => new RegExp(settings.apkFilterRegEx).test(u));
  check(`obtainium/${entry.app}: endpoint serves exactly one apk link`,
    page.ok && links.length === 1, `HTTP ${page.status}, ${links.length} link(s)`);
  check(`obtainium/${entry.app}: that link is the current build`, links[0] === entry.apk);

  const target = decodeURI(links[links.length - 1] ?? "");
  const matches = [...target.matchAll(new RegExp(settings.versionExtractionRegEx, "g"))];
  const got = matches.at(-1)?.[Number(settings.matchGroupToUse)];
  check(`obtainium/${entry.app}: version regex matches the whole APK URL`,
    matches.length > 0, matches.length ? `${matches.length} match(es)` : `NO MATCH against ${target}`);
  check(`obtainium/${entry.app}: extracted version is the app version`,
    got === entry.version, `${got} (want ${entry.version})`);

  const decoded = JSON.parse(decodeURIComponent(entry.deep_link.replace("obtainium://app/", "")));
  check(`obtainium/${entry.app}: deep link decodes to the same config`,
    decoded.url === cfg.url && decoded.id === cfg.id);
}

// The README carries the same one-tap links; they must not drift from the generated ones.
let readme = null;
try {
  readme = readFileSync(new URL("../README.md", import.meta.url), "utf8");
} catch {
  console.log("SKIP  obtainium: README drift check (run from inside the repo to enable it)");
}
if (readme !== null) {
  for (const a of index.apps) {
    check(`readme: Apps table has a row for ${a.id}`, readme.includes(`| **${a.name}** |`));
  }
  for (const e of obt.apps) {
    check(`readme: ${e.app} row carries its Obtainium badge`, readme.includes(`][obt-${e.app}]`));
  }
  check("obtainium: README add-all link matches the generated one", readme.includes(obt.add_all_url));
  for (const entry of obt.apps) {
    check(`obtainium/${entry.app}: README add link matches the generated one`,
      readme.includes(entry.add_url));
  }
}

// --- api tab ----------------------------------------------------------------
$$(".tab").find((t) => t.dataset.tab === "api")?.click();
await sleep(300);
const eps = $$("#api-body .ep");
check("api: endpoints listed", eps.length >= 4, `${eps.length} endpoint(s)`);
check("api: base url substituted in the example",
  ($(".api-base")?.textContent ?? "").startsWith("https://"), $(".api-base")?.textContent);

// --- no script errors -------------------------------------------------------
check("no script errors", consoleErrors.length === 0, consoleErrors.join(" | ").slice(0, 200));

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
