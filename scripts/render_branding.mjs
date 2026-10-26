// Renders branding/*.svg to the README's images, as PlayGuard's
// tools/render_branding.mjs does: .github/readme/banner.png (1280x320) and
// .github/readme/social-preview.png (1280x640, the repository's social
// preview, uploaded by hand in Settings › General), at twice their size.
// Needs Node and Playwright (Chromium); loads the Sora font from Google Fonts.
//   node scripts/render_branding.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const jobs = [
  { svg: 'branding/banner.svg', out: '.github/readme/banner.png', w: 1280, h: 320 },
  { svg: 'branding/social-preview.svg', out: '.github/readme/social-preview.png', w: 1280, h: 640 },
];

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const page = await browser.newPage({ deviceScaleFactor: 2 });
for (const job of jobs) {
  const svg = readFileSync(join(root, job.svg), 'utf8');
  await page.setViewportSize({ width: job.w, height: job.h });
  await page.setContent(`<!doctype html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&display=swap" rel="stylesheet">
<style>html,body{margin:0;background:transparent}</style></head><body>${svg}</body></html>`);
  await page.evaluate(() => document.fonts.ready);
  await page.locator('svg').first().screenshot({ path: join(root, job.out) });
  console.log(job.out);
}
await browser.close();
