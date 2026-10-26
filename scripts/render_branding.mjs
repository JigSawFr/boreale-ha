// Renders branding/*.svg to the README's images, as Aurore's
// .github/branding/render.mjs does (the same sky): .github/readme/banner.png
// (1280x320), .github/readme/social-preview.png (1280x640, the repository's
// social preview, uploaded by hand in Settings › General) and
// .github/readme/icon.png (256x256), at twice their size.
// Needs Node and Playwright (Chromium); loads Sora from Google Fonts.
//   node scripts/render_branding.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const jobs = [
  { svg: 'branding/icon.svg', out: '.github/readme/icon.png', w: 256, h: 256, transparent: true },
  { svg: 'branding/banner.svg', out: '.github/readme/banner.png', w: 1280, h: 320 },
  { svg: 'branding/social-preview.svg', out: '.github/readme/social-preview.png', w: 1280, h: 640 },
];

// <image href="icon.svg"> becomes the icon itself, inline.
const icon = readFileSync(join(root, 'branding/icon.svg'), 'utf8');
const inline = (svg) => svg.replace(/<image href="icon\.svg" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="[\d.]+"\/>/g,
  (_, x, y, w) => `<g transform="translate(${x} ${y}) scale(${w / 256})">${icon.replace(/<\/?svg[^>]*>/g, '')}</g>`);

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
for (const job of jobs) {
  const page = await browser.newPage({ viewport: { width: job.w, height: job.h }, deviceScaleFactor: 2 });
  const svg = inline(readFileSync(join(root, job.svg), 'utf8'));
  await page.setContent(`<!doctype html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;700&display=block" rel="stylesheet">
<style>html,body{margin:0;background:transparent}svg{display:block}</style></head><body>${svg}</body></html>`);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: join(root, job.out), omitBackground: !!job.transparent });
  await page.close();
  console.log(job.out);
}
await browser.close();
