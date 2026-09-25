// Visits each menu section, screenshots it and dumps every rendered table/grid to JSON.
const fs = require('fs');
const { BASE, launch } = require('./common');

async function dumpTables(page) {
  return page.$$eval('table', ts => ts.map(t => {
    const rows = [...t.querySelectorAll('tr')].map(r => [...r.querySelectorAll('th,td')].map(c => c.innerText.trim().replace(/\s+/g, ' ')));
    return { cls: t.className, rows: rows.filter(r => r.length) };
  }).filter(t => t.rows.length));
}

(async () => {
  const [stateFile, out, ...only] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  const sections = only.length ? only : ['DASHBOARD', 'TEAM SUMMARY', 'SQUAD LIST', 'FIXTURES', 'LEADERS', 'MATCH REPORTS', 'OPPOSITION ANALYSIS', 'PD DRAFT'];
  const { browser, page } = await launch(stateFile);
  await page.goto(BASE + '/', { waitUntil: 'load' });
  await page.waitForTimeout(15000);
  for (const name of sections) {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    try {
      const labels = await page.$$eval('button.tile', bs => bs.map(b => b.innerText.trim().toUpperCase()));
      const idx = labels.indexOf(name);
      if (idx < 0) throw new Error('tile not found; have: ' + labels.join(', '));
      const tile = page.locator('button.tile').nth(idx);
      const bb = await tile.boundingBox();
      if (!bb || bb.x < 0) { await page.mouse.click(22, 18); await page.waitForTimeout(2000); } // open slide-out menu
      await tile.click();
      await page.waitForTimeout(12000);
      await page.screenshot({ path: `${out}/${slug}.png`, fullPage: true });
      fs.writeFileSync(`${out}/${slug}.html`, await page.content());
      const tables = await dumpTables(page);
      fs.writeFileSync(`${out}/${slug}.json`, JSON.stringify({ url: page.url(), tables }, null, 1));
      console.log(name, page.url(), 'tables:', tables.length, tables.map(t => t.rows.length).join(','));
    } catch (e) { console.log(name, 'ERR', e.message.split('\n')[0]); }
  }
  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
