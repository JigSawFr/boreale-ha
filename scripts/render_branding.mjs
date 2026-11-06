// Renders what Boréale for HA draws only for itself: the logos Home
// Assistant shows (custom_components/boreale/brand/logo.png and dark_logo.png,
// 1065x256, each at @2x too). The icon, the mark, brand/icon.png and
// icon@2x.png, the site's icons and favicons, the README's banner and icon and
// the social preview come from Boréale's brand kit (JigSawFr/boreale,
// branding/ha/, copied by its tools/sync_branding.py).
// Needs Node and Playwright (Chromium); loads Sora from Google Fonts.
//   node scripts/render_branding.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const BRAND = 'custom_components/boreale/brand/';
const jobs = [
  { svg: 'branding/logo.svg', out: BRAND + 'logo.png', w: 1065, h: 256, scale: 1, transparent: true },
  { svg: 'branding/logo.svg', out: BRAND + 'logo@2x.png', w: 1065, h: 256, scale: 2, transparent: true },
  { svg: 'branding/logo-dark.svg', out: BRAND + 'dark_logo.png', w: 1065, h: 256, scale: 1, transparent: true },
  { svg: 'branding/logo-dark.svg', out: BRAND + 'dark_logo@2x.png', w: 1065, h: 256, scale: 2, transparent: true },
];

const icon = readFileSync(join(root, 'branding/icon.svg'), 'utf8').replace(/<\/?svg[^>]*>/g, '');
const inline = (svg) => svg.replace(/<image href="icon\.svg" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="[\d.]+"\/>/g,
  (_, x, y, w) => `<svg x="${x}" y="${y}" width="${w}" height="${w}" viewBox="0 0 256 256"><clipPath id="icon-round"><rect width="256" height="256" rx="56"/></clipPath><g clip-path="url(#icon-round)">${icon}</g></svg>`);

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
for (const job of jobs) {
  const page = await browser.newPage({ viewport: { width: job.w, height: job.h }, deviceScaleFactor: job.scale });
  const svg = inline(job.svg.startsWith('<svg') ? job.svg : readFileSync(join(root, job.svg), 'utf8'));
  await page.setContent(`<!doctype html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;700&display=block" rel="stylesheet">
<style>html,body{margin:0;background:transparent}svg{display:block}</style></head><body>${svg}</body></html>`);
  await page.evaluate(async () => {
    await document.fonts.load('700 30px Sora');
    await document.fonts.load('400 20px Sora');
    await document.fonts.load('300 20px Sora');
    await document.fonts.ready;
  });
  await page.screenshot({ path: join(root, job.out), omitBackground: !!job.transparent });
  await page.close();
  console.log(job.out);
}
await browser.close();
