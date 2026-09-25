// Renders the coach report pages in report/coach/*.html to A4 PDFs (light theme, backgrounds on).
// Usage: NODE_PATH=$(npm root -g) node analysis/render_pdf.js
const fs = require('fs');
const path = require('path');
const { launch } = require('../scraper/common');

(async () => {
  const dir = path.resolve('report/coach');
  const { browser, page } = await launch();
  await page.emulateMedia({ colorScheme: 'light', media: 'print' });
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.html'))) {
    const body = fs.readFileSync(path.join(dir, f), 'utf8');
    const doc = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
      <style>body{margin:0} img{max-width:100%}</style></head><body>${body}</body></html>`;
    await page.setContent(doc, { waitUntil: 'load' });
    await page.waitForTimeout(2500); // web fonts
    const out = path.join(dir, f.replace(/\.html$/, '.pdf'));
    await page.pdf({ path: out, format: 'A4', printBackground: true, margin: { top: '14mm', bottom: '14mm', left: '10mm', right: '10mm' } });
    await page.setViewportSize({ width: 800, height: 1000 });
    await page.screenshot({ path: out.replace(/\.pdf$/, '.preview.png'), fullPage: true });
    console.log('wrote', out);
  }
  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
