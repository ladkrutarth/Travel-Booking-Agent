import { expect, test } from "@playwright/test";

test("signup through confirm", async ({ page }) => {
  const email = `e2e_${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.fill("#full_name", "E2E User");
  await page.fill("#email", email);
  await page.fill("#password", "password123");
  await page.click("button[type=submit]");
  await page.waitForURL("**/dashboard");
  await page.click("text=New trip");
  await page.fill("#origin", "JFK");
  await page.fill("#destination", "LAX");
  await page.fill("#destination_city", "Los Angeles");
  await page.fill("#budget_usd", "2000");
  await page.click("button[type=submit]");
  await page.waitForURL("**/trips/**");
  await expect(page.getByRole("heading", { name: "Compare offers" })).toBeVisible({
    timeout: 20000,
  });
  await page.locator(".offer").first().click();
  await page.locator("div").filter({ has: page.getByRole("heading", { name: "Hotels" }) }).locator(".offer").first().click();
  await page.click("text=Continue with selection");
  await page.fill("input[name=first_name_0]", "Alex");
  await page.fill("input[name=last_name_0]", "Traveler");
  await page.click("text=Save travelers");
  await page.click("text=Approve & book");
  await expect(page.getByRole("heading", { name: "Booking confirmed" })).toBeVisible({
    timeout: 20000,
  });
});
