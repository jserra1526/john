const { launch, login } = require('./common');
const fs = require('fs');
(async () => {
  const out = process.argv[2];
  fs.mkdirSync(out, { recursive: true });
  const { browser, page } = await launch();
  await login(page);
  console.log('URL after login:', page.url());
  await page.screenshot({ path: `${out}/home.png`, fullPage: true });
  const links = await page.$$eval('a', as => as.map(a => ({ text: a.innerText.trim(), href: a.getAttribute('href') })));
  console.log(JSON.stringify(links, null, 1));
  fs.writeFileSync(`${out}/home.html`, await page.content());
  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
