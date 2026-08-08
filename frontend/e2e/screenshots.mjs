/**
 * Regenerate the screenshots the README embeds.
 *
 *   node e2e/screenshots.mjs                        # against the Compose stack
 *   KURA_BASE_URL=http://localhost:5173 node e2e/screenshots.mjs
 *
 * Kept as a script rather than a test because it asserts nothing: it signs in
 * as the demo account and photographs each page. Run it after any visual
 * change so the README stops showing a version of the app that no longer
 * exists.
 */
import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE = process.env.KURA_BASE_URL || "http://localhost:3000";
const OUT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../docs/screenshots"
);

const SHOTS = [
  { file: "01-discover.png", path: "/", wait: ".tile-grid" },
  { file: "03-for-you.png", path: "/recommendations", wait: ".tile-grid" },
  { file: "04-watching.png", path: "/watching" },
  { file: "06-shelf.png", path: "/shelf" },
  { file: "07-insights.png", path: "/insights" },
  { file: "08-collections.png", path: "/collections" },
  { file: "09-seasons.png", path: "/seasons", wait: ".season-grid" },
  { file: "10-social.png", path: "/social" },
  { file: "11-admin.png", path: "/admin" },
  { file: "12-settings.png", path: "/settings" },
  { file: "13-upcoming.png", path: "/upcoming", wait: ".airing-card" },
];

async function signIn(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', "demo@anime.app");
  await page.fill('input[type="password"]', "demo1234");
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20000 });
}

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});

// The logged-out shot has to happen before signing in.
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(OUT, "02-login.png") });
console.log("02-login.png");

await signIn(page);

for (const shot of SHOTS) {
  await page.goto(`${BASE}${shot.path}`, { waitUntil: "networkidle" });
  if (shot.wait) {
    await page.waitForSelector(shot.wait, { timeout: 20000 }).catch(() => {});
  }
  // Let poster art decode and the entrance animations settle, otherwise cards
  // are photographed mid-fade and the whole grid looks broken.
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(OUT, shot.file) });
  console.log(shot.file);
}

// A detail page needs a real id, so take whatever Discover is showing first.
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
const href = await page.locator('.tile-poster[href^="/anime/"]').first().getAttribute("href");
if (href) {
  await page.goto(`${BASE}${href}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(OUT, "05-detail.png") });
  console.log("05-detail.png");
}

await browser.close();
console.log(`\nWrote to ${OUT}`);
