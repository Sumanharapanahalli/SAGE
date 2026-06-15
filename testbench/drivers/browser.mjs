/**
 * Generic headless-Chromium UI smoke (Playwright). Driven by a JSON config passed
 * as argv[2] (see drivers/browser.py). Loads the URL, clicks each declared view,
 * checks no console/page errors, runs optional click+assert interactions, and
 * prints a final JSON line: {checks:[{name,ok,detail}]}.
 *
 * Run from a dir with `node_modules/playwright`:
 *   node browser.mjs '{"url":"http://localhost:8000","views":[...]}'
 */
import { chromium } from 'playwright';

const cfg = JSON.parse(process.argv[2] || '{}');
const url = cfg.url || 'http://localhost:8000';
const checks = [];
const IGNORE = [/favicon/i];
let current = 'load';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error' && !IGNORE.some((r) => r.test(m.text()))) errors.push({ view: current, text: m.text() }); });
page.on('pageerror', (e) => errors.push({ view: current, text: 'PAGEERROR: ' + e.message }));

try {
  const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  checks.push({ name: `load ${url}`, ok: !!(resp && resp.ok()), detail: 'HTTP ' + (resp ? resp.status() : '?') });
  await page.waitForTimeout(800);

  for (const v of cfg.views || []) {
    current = v.name;
    const before = errors.length;
    try {
      if (v.click) await page.click(v.click, { timeout: 5000 });
      await page.waitForTimeout(v.wait || 1000);
      const newErr = errors.length - before;
      checks.push({ name: `view '${v.name}' renders`, ok: newErr === 0, detail: newErr ? `${newErr} console error(s)` : 'clean' });
    } catch (e) {
      checks.push({ name: `view '${v.name}' renders`, ok: false, detail: e.message });
    }
  }

  for (const it of cfg.interactions || []) {
    current = it.name;
    try {
      if (it.goto_view) await page.click(it.goto_view, { timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(500);
      if (it.click) await page.click(it.click, { timeout: 5000 });
      await page.waitForTimeout(it.wait || 1500);
      let ok = true, detail = 'done';
      if (it.expect_selector) {
        const txt = (await page.textContent(it.expect_selector).catch(() => '')) || '';
        ok = txt.trim().length > 0; detail = txt.slice(0, 60);
      }
      checks.push({ name: `interaction '${it.name}'`, ok, detail });
    } catch (e) {
      checks.push({ name: `interaction '${it.name}'`, ok: false, detail: e.message });
    }
  }
} finally {
  await browser.close();
}

const fails = checks.filter((c) => !c.ok).length;
console.error(`browser: ${checks.length - fails}/${checks.length} ok, ${errors.length} console error(s)`);
console.log(JSON.stringify({ checks }));
process.exit(fails ? 1 : 0);
