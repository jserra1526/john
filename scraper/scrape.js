// Extracts the Premier Data tables this account can see into CSVs.
// Usage: node scrape.js <storageState.json> <outDir>   (run auth.js first to create the state file)
const fs = require('fs');
const path = require('path');
const { BASE, launch } = require('./common');

const clean = s => s.replace(/Press Enter to sort\. Press Alt Down to open filter Menu/g, '').replace(/\s+/g, ' ').trim();

async function tables(page) {
  return page.$$eval('table', ts => ts.map(t => [...t.querySelectorAll('tr')]
    .map(r => [...r.querySelectorAll('th,td')].map(c => c.innerText))).filter(t => t.length));
}

// Syncfusion grids render the header and body as separate <table>s: pair a 1-row header with the next body table.
function grids(raw) {
  const out = [];
  for (let i = 0; i < raw.length; i++) {
    if (raw[i].length === 1 && raw[i + 1]) { out.push([raw[i][0].map(clean), ...raw[i + 1].map(r => r.map(clean))]); i++; }
  }
  return out;
}

function writeCsv(file, rows) {
  const esc = v => /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
  fs.writeFileSync(file, rows.map(r => r.map(v => esc(String(v ?? ''))).join(',')).join('\n') + '\n');
  console.log('wrote', path.basename(file), rows.length - 1, 'rows');
}

// Drop presentation-only columns (e.g. the Vision icon column, internal ids).
function dropCols(rows, names) {
  const keep = rows[0].map((h, i) => !names.includes(h) ? i : -1).filter(i => i >= 0);
  return rows.map(r => keep.map(i => r[i]));
}

async function openPage(page, url, wait = 15000) {
  await page.goto(BASE + url, { waitUntil: 'load' });
  await page.waitForTimeout(wait);
}

async function teamSummary(page, out, shots) {
  await openPage(page, '/TeamSummary/8591');
  await page.screenshot({ path: `${shots}/team-summary.png`, fullPage: true });
  let g = grids(await tables(page));
  writeCsv(`${out}/team_season_for_vs_against.csv`, g.find(t => t[0][0] === 'Stat Type'));
  for (const mode of ['For', 'Against', 'Differential']) {
    await page.getByRole('button', { name: mode, exact: true }).click();
    await page.waitForTimeout(4000);
    g = grids(await tables(page));
    writeCsv(`${out}/team_match_stats_${mode.toLowerCase()}.csv`, dropCols(g.find(t => t[0][0] === 'Opponent'), ['Vision']));
  }
  await page.getByText('Player Statistics', { exact: true }).click();
  await page.waitForTimeout(6000);
  await page.screenshot({ path: `${shots}/team-summary-players.png`, fullPage: true });
  g = grids(await tables(page));
  const players = g.find(t => t[0][0] === 'Name');
  players[0].unshift('Number');
  for (const r of players.slice(1)) { const m = r[0].match(/^(\d+)\.\s*(.*)$/); r.splice(0, 1, m ? m[1] : '', m ? m[2] : r[0]); }
  writeCsv(`${out}/player_season_averages.csv`, players);
}

// The leaderboard grid is virtualised (only ~25 rows exist in the DOM), so scroll it and merge rows by name.
async function scrollGrid(page) {
  const header = grids(await tables(page)).find(t => t[0][0] === 'Rank');
  if (!header) return null;
  const rows = new Map();
  let lastSize = -1, stale = 0;
  for (let step = 0; step < 800 && stale < 6; step++) {
    const g = grids(await tables(page)).find(t => t[0][0] === 'Rank');
    for (const r of g.slice(1)) if (r[0]) rows.set(r[1] + '|' + r[2], r); // ranks can tie, so key by name + team
    stale = rows.size === lastSize ? stale + 1 : 0;
    lastSize = rows.size;
    await page.$eval('.e-gridcontent .e-content', el => { el.scrollTop += el.clientHeight * 0.35; });
    await page.waitForTimeout(1200);
  }
  await page.$eval('.e-gridcontent .e-content', el => { el.scrollTop = 0; });
  return [header[0], ...[...rows.values()].sort((a, b) => Number(a[0]) - Number(b[0]))];
}

// Leaderboard toggles are disabled while selected, so only click the ones that are not.
async function select(page, label) {
  const b = page.locator('.header-buttons-group button', { hasText: new RegExp(`^${label}$`, 'i') }).first();
  if (await b.isEnabled()) { await b.click(); await page.waitForTimeout(8000); }
}

async function leaders(page, out, shots) {
  await openPage(page, '/Leaders');
  for (const who of ['TEAMS', 'PLAYERS']) {
    for (const agg of ['AVERAGES', 'TOTALS']) {
      await select(page, who);
      await select(page, agg);
      const slug = `leaders_${who.toLowerCase()}_${agg.toLowerCase()}`;
      await page.screenshot({ path: `${shots}/${slug}.png`, fullPage: true });
      const g = await scrollGrid(page);
      if (!g) { console.log('no grid for', slug); continue; }
      writeCsv(`${out}/${slug}.csv`, dropCols(g, ['Id', 'ID']));
    }
  }
}

async function fixtures(page, out, shots) {
  await openPage(page, '/Fixtures');
  const rows = [['Round', 'Date', 'HomeTeam', 'HomeScore', 'HomeGB', 'AwayTeam', 'AwayScore', 'AwayGB']];
  const roundButtons = page.locator('.footer .flex.around button');
  const labels = await roundButtons.allInnerTexts();
  for (let i = 0; i < labels.length; i++) {
    await roundButtons.nth(i).click();
    await page.waitForTimeout(5000);
    const cards = await page.$$eval('button.card.fixture', cs => cs.map(c => {
      const q = s => c.querySelector(s)?.innerText.trim() ?? '';
      const scores = [...c.querySelectorAll('.result .score')].map(x => [...x.querySelectorAll('p')].map(p => p.innerText.trim()));
      return [q('.head h4'), q('.body > .home .team-name'), scores[0]?.[0], scores[0]?.[1], q('.body > .away .team-name'), scores[1]?.[0], scores[1]?.[1]];
    }));
    for (const c of cards) rows.push([labels[i].trim(), ...c]);
    console.log('round', labels[i], cards.length, 'fixtures');
  }
  writeCsv(`${out}/fixtures_results.csv`, rows);
}

// Per-game player stats for every match our team played (both sides), from FixtureSummary > Player Stats.
async function matchPlayerStats(page, out, shots, team = 'SHEPPARTON UNITED') {
  const games = [];
  const clubs = {};
  await openPage(page, '/Fixtures');
  const labels = (await page.locator('.footer .flex.around button').allInnerTexts()).map(s => s.trim());
  for (let i = 0; i < labels.length; i++) {
    if (!page.url().endsWith('/Fixtures')) await openPage(page, '/Fixtures');
    await page.locator('.footer .flex.around button').nth(i).click();
    await page.waitForTimeout(5000);
    Object.assign(clubs, Object.fromEntries(await page.$$eval('button.card.fixture img', is => is.map(i => [i.src.match(/clubs\/(\d+)\//)?.[1], i.alt]))));
    const card = page.locator('button.card.fixture', { hasText: new RegExp(team, 'i') }).first();
    if (!(await card.count())) { console.log('round', labels[i], 'no game'); continue; }
    await card.locator('button[title="Match Statistics"]').click();
    await page.waitForTimeout(3000);
    const id = page.url().match(/FixtureSummary\/(\d+)/)?.[1];
    const names = await card.locator('.team-name').allInnerTexts().catch(() => []);
    const opponent = names.map(n => n.trim()).find(n => n.toUpperCase() !== team.toUpperCase()) ?? '';
    games.push({ round: labels[i], id, opponent });
    console.log('round', labels[i], 'fixture', id);
  }
  const rows = [];
  let header;
  // Our club id is the logo shared by every game; anything else unmapped is that game's opponent.
  let ourClub;
  for (const g of games) {
    await openPage(page, `/FixtureSummary/${g.id}`, 12000);
    await page.getByText('Player Stats', { exact: true }).click();
    await page.waitForTimeout(7000);
    const data = await page.$$eval('table', ts => ts.map(t => [...t.querySelectorAll('tr')].map(r => [...r.querySelectorAll('th,td')].map(c => {
      const img = c.querySelector('img');
      return img ? (img.src.match(/clubs\/(\d+)\//)?.[1] ?? '') : c.innerText.trim().replace(/\s+/g, ' ');
    }))).filter(t => t.length));
    const hi = data.findIndex(t => t.length === 1 && t[0].includes('Name'));
    if (hi < 0) { console.log('no player grid for', g.id); continue; }
    ourClub ??= Object.keys(clubs).find(k => clubs[k].toUpperCase() === team.toUpperCase());
    header ??= ['Round', 'FixtureId', 'Team', 'Number', 'Name', ...data[hi][0].slice(2)];
    for (const r of data[hi + 1]) {
      const m = r[1].match(/^(\d+)\s+(.*)$/);
      rows.push([g.round, g.id, clubs[r[0]] || (r[0] === ourClub ? team : g.opponent), m ? m[1] : '', m ? m[2] : r[1], ...r.slice(2)]);
    }
    console.log('fixture', g.id, 'players', data[hi + 1].length);
  }
  writeCsv(`${out}/match_player_stats.csv`, [header, ...rows]);
}

(async () => {
  const [stateFile, out = 'data', shots = 'report/screenshots', ...only] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  fs.mkdirSync(shots, { recursive: true });
  const { browser, page } = await launch(stateFile);
  const steps = { teamSummary, leaders, fixtures, matchPlayerStats };
  for (const [name, fn] of Object.entries(steps)) {
    if (only.length && !only.includes(name)) continue;
    try { await fn(page, out, shots); } catch (e) { console.log(name, 'ERR', e.message.split('\n')[0]); }
  }
  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
