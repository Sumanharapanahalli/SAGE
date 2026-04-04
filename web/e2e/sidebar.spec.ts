import { test, expect } from '@playwright/test'

test.describe('Sidebar Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForTimeout(500)
  })

  test('sidebar has all major navigation areas', async ({ page }) => {
    const sidebar = page.locator('nav').first()
    const text = await page.textContent('body')
    // Check for nav area labels
    for (const area of ['Work', 'Intelligence', 'Knowledge', 'Admin']) {
      expect(text).toContain(area)
    }
  })

  test('clicking Chat navigates to /chat', async ({ page }) => {
    const chatLink = page.locator('a[href="/chat"]')
    if (await chatLink.count() > 0) {
      await chatLink.first().click()
      await page.waitForTimeout(300)
      expect(page.url()).toContain('/chat')
    }
  })

  test('clicking Queue navigates to /queue', async ({ page }) => {
    const queueLink = page.locator('a[href="/queue"]')
    if (await queueLink.count() > 0) {
      await queueLink.first().click()
      await page.waitForTimeout(300)
      expect(page.url()).toContain('/queue')
    }
  })

  test('clicking Agents navigates to /agents', async ({ page }) => {
    const link = page.locator('a[href="/agents"]')
    if (await link.count() > 0) {
      await link.first().click()
      await page.waitForTimeout(300)
      expect(page.url()).toContain('/agents')
    }
  })

  test('clicking Safety Analysis navigates to /safety', async ({ page }) => {
    const link = page.locator('a[href="/safety"]')
    if (await link.count() > 0) {
      await link.first().click()
      await page.waitForTimeout(300)
      expect(page.url()).toContain('/safety')
    }
  })

  test('clicking Settings navigates to /settings', async ({ page }) => {
    const link = page.locator('a[href="/settings"]')
    if (await link.count() > 0) {
      await link.first().click()
      await page.waitForTimeout(300)
      expect(page.url()).toContain('/settings')
    }
  })
})
