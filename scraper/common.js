// Shared Playwright setup for Premier Data (Blazor Server). Credentials come from env only.
const { execSync } = require('child_process');
const { chromium } = require('playwright');

const BASE = 'https://pdapp2.advancedhp.com.au';

function proxySpki() {
  return execSync(
    "openssl x509 -in /root/.ccr/agent-proxy-ca.crt -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64"
  ).toString().trim();
}

async function launch(stateFile) {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    proxy: { server: process.env.HTTPS_PROXY },
    args: [`--ignore-certificate-errors-spki-list=${proxySpki()}`],
  });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, acceptDownloads: true,
    ...(stateFile ? { storageState: stateFile } : {}) });
  const page = await context.newPage();
  return { browser, context, page };
}

async function login(page) {
  if (!process.env.PD_USERNAME || !process.env.PD_PASSWORD) throw new Error('PD_USERNAME / PD_PASSWORD not set');
  await page.goto(`${BASE}/Auth/Login`, { waitUntil: 'load' });
  await page.waitForTimeout(3000);
  const user = page.locator('input[name*="ser" i], input[id*="ser" i], input[type="text"], input[type="email"]').first();
  const pass = page.locator('input[type="password"]').first();
  await user.fill(process.env.PD_USERNAME);
  await pass.fill(process.env.PD_PASSWORD);
  await page.getByRole('button', { name: /login/i }).first().click();
  await page.waitForTimeout(6000);
}

module.exports = { BASE, launch, login };
