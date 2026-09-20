// Flow test: drive the published page exactly as a visitor would, against the LIVE site.
// jsdom runs the real app.js; fetch hits the real Pages origin.
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
const cards = $$("#apps .card");
check("builds: a card rendered", cards.length > 0, `${cards.length} card(s)`);

const card = cards[0];
const title = card?.querySelector("h2 span")?.textContent ?? "";
check("builds: app name from config.toml", title === "YouTube", `got "${title}"`);
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
