import { expect, test } from "@playwright/test";

const DEMO = { email: "demo@anime.app", password: "demo1234" };

async function signIn(page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', DEMO.email);
  await page.fill('input[type="password"]', DEMO.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/recommendations/);
}

test.describe("Kura smoke", () => {
  test("discover renders posters without signing in", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".panel-head h1")).toBeVisible();
    await expect(page.locator(".tile").first()).toBeVisible();
    // A blank screen from a JS crash is the failure mode this whole suite exists for.
    await expect(page.locator(".tile")).not.toHaveCount(0);
  });

  test("search finds a well known title", async ({ page }) => {
    await page.goto("/");
    await page.fill('input[aria-label="Search anime"]', "cowboy bebop");
    await page.getByRole("button", { name: "Go" }).click();
    await expect(page.locator(".tile-body h3").first()).toContainText(/cowboy bebop/i);
  });

  test("demo login lands on personalized picks", async ({ page }) => {
    await signIn(page);
    await expect(page.getByText(/Picks for demo/i)).toBeVisible();
    await expect(page.locator(".tile").first()).toBeVisible();
  });

  test("recommendations explain themselves", async ({ page }) => {
    await signIn(page);
    // The main grid, not the sequence rail above it.
    const reason = page.locator(".tile-grid").last().locator(".reason").first();
    await expect(reason).toBeVisible();
    await expect(reason).toContainText(/because you liked|rated highly|themes you keep|popular/i);
  });

  test("plus one episode moves progress", async ({ page }) => {
    await signIn(page);
    await page.goto("/watching");
    const card = page.locator(".watch-card").first();
    await expect(card).toBeVisible();

    const before = await card.locator(".meta").innerText();
    await card.getByRole("button", { name: "+1 ep" }).click();
    await expect(page.locator(".toast-float")).toBeVisible();
    await expect(async () => {
      const after = await page.locator(".watch-card").first().locator(".meta").innerText();
      expect(after).not.toEqual(before);
    }).toPass();
  });

  test("rating a title saves and marks it completed", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    // Only cards in the main grid carry a rate strip. Wait for the rail to
    // finish swapping the grid in, otherwise the tile detaches mid-action.
    const tile = page.locator(".tile-grid").last().locator(".tile").first();
    await expect(tile).toBeVisible();
    await page.waitForTimeout(300);
    await tile.hover();
    await tile.getByRole("button", { name: "Rate 9 out of 10" }).click();
    await expect(page.locator(".toast-float")).toContainText(/saved 9/i);
  });

  test("watch session counts attention and can be closed", async ({ page }) => {
    await signIn(page);
    await page.goto("/watching");
    await page.locator(".watch-card").first().getByRole("button", { name: "Timer" }).click();

    const hud = page.locator(".watch-hud");
    await expect(hud).toBeVisible();
    await expect(hud).toContainText(/counting|paused/);
    await expect(hud.locator(".hud-dial strong")).toContainText(/\d+:\d\d/);

    await hud.getByRole("button", { name: "End" }).click();
    await expect(page.locator(".toast-float")).toContainText(/session closed/i);
  });

  test("command palette opens and finds a title", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await page.keyboard.press("Control+k");
    const palette = page.getByRole("dialog", { name: "Command palette" });
    await expect(palette).toBeVisible();

    await palette.getByRole("textbox").fill("steins");
    await expect(palette.getByRole("option").first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(palette).toBeHidden();
  });

  test("not interested hides a title from the grid", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    const tile = page.locator(".tile-grid").last().locator(".tile").first();
    await expect(tile).toBeVisible();
    await page.waitForTimeout(300);
    const animeId = await tile.getAttribute("data-anime-id");

    await tile.hover();
    await tile.locator(".tile-tools button").first().click();
    await tile.getByRole("menuitem", { name: "Not interested" }).click();

    await expect(page.locator(".toast-float")).toContainText(/hidden/i);
    await expect(page.locator(`[data-anime-id="${animeId}"]`)).toHaveCount(0);
  });

  test("insights show the streak, health, and taste panels", async ({ page }) => {
    await signIn(page);
    await page.goto("/insights");
    await expect(page.getByRole("heading", { name: /Watch streak/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Vault health/ })).toBeVisible();
    await expect(page.locator(".heatmap svg")).toBeVisible();
    await expect(page.locator(".stat-tile").first()).toBeVisible();
  });

  test("collections list opens a shelf", async ({ page }) => {
    await signIn(page);
    await page.goto("/collections");
    const card = page.locator(".collection-card").first();
    await expect(card).toBeVisible();
    await card.locator("h3 a").click();
    await expect(page).toHaveURL(/\/collections\/\d+/);
    await expect(page.locator(".panel-head h1")).toBeVisible();
  });

  test("season calendar loads a season", async ({ page }) => {
    await page.goto("/seasons");
    const cell = page.locator(".season-cell:not(.empty)").first();
    await expect(cell).toBeVisible();
    await cell.click();
    await expect(page.locator(".tile").first()).toBeVisible();
  });

  test("instance dashboard reports live numbers", async ({ page }) => {
    await signIn(page);
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: /Operator dashboard/ })).toBeVisible();
    await expect(page.locator(".stat-tile").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: /Feature flags/ })).toBeVisible();
  });

  test("no page in the app logs a console error", async ({ page }) => {
    const errors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    page.on("pageerror", (err) => errors.push(String(err)));

    await signIn(page);
    for (const path of [
      "/",
      "/watching",
      "/recommendations",
      "/collections",
      "/insights",
      "/seasons",
      "/social",
      "/shelf",
      "/library",
      "/settings",
      "/quiz",
      "/admin",
    ]) {
      await page.goto(path);
      // A bounce back to /login means the session was dropped, which is the
      // regression this assertion exists to catch.
      await expect(page.locator("main"), `${path} did not render`).toBeVisible();
    }

    // Poster CDNs go down sometimes and that is not our bug.
    const real = errors.filter(
      (e) => !/favicon|ERR_|net::|Failed to load resource|manifest/i.test(e)
    );
    expect(real, `console errors: ${real.join(" | ")}`).toHaveLength(0);
  });
});
