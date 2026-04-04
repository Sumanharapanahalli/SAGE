import { test, expect } from '@playwright/test'

test.describe('PWA Configuration', () => {
  test('manifest.json has correct structure', async ({ page }) => {
    const res = await page.goto('/manifest.json')
    expect(res?.status()).toBe(200)
    const manifest = await res?.json()

    expect(manifest.name).toBe('SAGE — Smart Agentic-Guided Empowerment')
    expect(manifest.short_name).toBe('SAGE')
    expect(manifest.display).toBe('standalone')
    expect(manifest.background_color).toBe('#0a0a0c')
    expect(manifest.theme_color).toBe('#3b82f6')
    expect(manifest.start_url).toBe('/')
    expect(manifest.icons).toBeDefined()
    expect(manifest.icons.length).toBeGreaterThan(0)
  })

  test('index.html has PWA meta tags', async ({ page }) => {
    await page.goto('/')
    // Theme color meta tag
    const themeColor = page.locator('meta[name="theme-color"]')
    await expect(themeColor).toHaveAttribute('content', '#3b82f6')

    // Apple meta tags
    const appleCapable = page.locator('meta[name="apple-mobile-web-app-capable"]')
    await expect(appleCapable).toHaveAttribute('content', 'yes')

    // Manifest link
    const manifestLink = page.locator('link[rel="manifest"]')
    await expect(manifestLink).toHaveAttribute('href', '/manifest.json')
  })

  test('icon SVG is a valid SVG', async ({ page }) => {
    const res = await page.goto('/icons/icon.svg')
    expect(res?.status()).toBe(200)
    const text = await res?.text()
    expect(text).toContain('<svg')
    expect(text).toContain('SAGE'.charAt(0)) // Contains the "S" letter
  })

  test('html title is SAGE', async ({ page }) => {
    await page.goto('/')
    const title = await page.title()
    expect(title).toContain('SAGE')
  })
})
