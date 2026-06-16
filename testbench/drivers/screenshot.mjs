/**
 * Headless screenshot of a URL (Playwright). Used by the Gemini visual UI
 * evaluator so Gemini can "see" a running web interface the same way Claude does
 * via the browser tools.
 *
 *   node screenshot.mjs <url> <out.png> [width] [height] [fullPage:0|1]
 */
import { chromium } from 'playwright';

const [, , url, out, w = '1400', h = '900', full = '1'] = process.argv;
if (!url || !out) {
  console.error('usage: node screenshot.mjs <url> <out.png> [w] [h] [fullPage]');
  process.exit(2);
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: +w, height: +h } });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: out, fullPage: full === '1' });
  console.log(out);
} finally {
  await browser.close();
}
