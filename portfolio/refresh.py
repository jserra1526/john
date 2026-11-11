"""Refresh the share portfolio tracker.

1. Imports every CommSec CSV in the "CommSec Exports" folder (duplicates across files are ignored).
2. Downloads current prices, company names and dividend history from Yahoo Finance (ASX data, TICKER.AX).
3. Works out each dividend you were entitled to (units held at the ex-dividend date x dividend per share).
4. Writes it all into share-portfolio-tracker.xlsx and opens it.

Run it by double-clicking "Refresh Portfolio.bat". Excel must be closed while it runs.
"""
from __future__ import annotations

import csv
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

import build_portfolio as bp

HERE = Path(__file__).resolve().parent
WORKBOOK = HERE / "share-portfolio-tracker.xlsx"
EXPORTS = HERE / "CommSec Exports"

# CommSec's Transactions export dates each trade on its settlement date (cash moves at settlement).
# With T+2 settlement, units bought before the ex-date settle by the day after it.
# Set to False if your export shows trade dates instead.
COMMSEC_DATE_IS_SETTLEMENT = True

TRADE_RE = re.compile(r"^\s*([BS])\s+([\d,]+)\s+([A-Z0-9.]+)\s+@\s+([\d.,]+)", re.I)


# ----------------------------------------------------------------------------- helpers
def to_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date {s!r}")


def to_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(",", "")
    if s in ("", "-"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    n = float(s.strip("()"))
    return -n if neg else n


def next_business_day(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def entitled(trade_date, ex_date, settlement=COMMSEC_DATE_IS_SETTLEMENT):
    """Did a trade dated trade_date count towards a dividend with this ex-date?"""
    if settlement:
        return trade_date <= next_business_day(ex_date)
    return trade_date < ex_date


# ----------------------------------------------------------------------------- CommSec CSV
def read_commsec_csv(path: Path):
    """Return raw rows: dicts with date, reference, details, debit, credit, balance."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    # find the header line (some exports have a title line first)
    start = next((i for i, l in enumerate(lines) if "details" in l.lower() and "date" in l.lower()), None)
    if start is None:
        raise ValueError(f"{path.name}: no header row with 'Date' and 'Details' found")
    reader = csv.reader(lines[start:])
    header = [h.strip().lower() for h in next(reader)]

    def col(*names):
        for i, h in enumerate(header):
            if any(h.startswith(n) for n in names):
                return i
        return None

    ix = {k: col(*v) for k, v in {
        "date": ("date",), "reference": ("reference", "ref"), "details": ("details", "description"),
        "debit": ("debit",), "credit": ("credit",), "balance": ("balance",)}.items()}
    if ix["date"] is None or ix["details"] is None:
        raise ValueError(f"{path.name}: needs Date and Details columns, found {header}")
    rows = []
    for rec in reader:
        if not rec or not any(x.strip() for x in rec):
            continue
        get = lambda k: rec[ix[k]].strip() if ix[k] is not None and ix[k] < len(rec) else ""
        rows.append({
            "date": to_date(get("date")), "reference": get("reference"), "details": get("details"),
            "debit": to_num(get("debit")), "credit": to_num(get("credit")), "balance": to_num(get("balance")),
        })
    return rows


def load_exports(folder: Path):
    files = sorted(folder.glob("*.csv")) if folder.exists() else []
    seen, rows = set(), []
    for fpath in files:
        for r in read_commsec_csv(fpath):
            key = (r["date"], r["reference"], r["details"], r["debit"], r["credit"])
            if key not in seen:
                seen.add(key)
                rows.append(r)
    rows.sort(key=lambda r: r["date"], reverse=True)
    return files, rows


def parse_trade(details):
    m = TRADE_RE.match(details or "")
    if not m:
        return None
    side, units, ticker, price = m.groups()
    return ("Buy" if side.upper() == "B" else "Sell", float(units.replace(",", "")), ticker.upper(),
            float(price.replace(",", "")))


# ----------------------------------------------------------------------------- data source
class YahooSource:
    """Prices, names and dividends from Yahoo Finance (which carries ASX data)."""

    def __init__(self):
        import yfinance as yf  # imported here so tests can run without it
        self.yf = yf

    def _retry(self, fn, tries=3):
        for i in range(tries):
            try:
                return fn()
            except Exception:
                if i == tries - 1:
                    raise
                time.sleep(2 * (i + 1))

    def price(self, code):
        h = self._retry(lambda: self.yf.Ticker(code).history(period="10d", auto_adjust=False))
        h = h.dropna(subset=["Close"])
        if h.empty:
            raise ValueError("no price data")
        return float(h["Close"].iloc[-1]), h.index[-1].date()

    def name(self, code):
        info = self._retry(lambda: self.yf.Ticker(code).info) or {}
        return info.get("longName") or info.get("shortName")

    def dividends(self, code):
        s = self._retry(lambda: self.yf.Ticker(code).dividends)
        return [(idx.date(), float(v)) for idx, v in s.items() if v]


# ----------------------------------------------------------------------------- workbook update
def refresh(workbook: Path, exports: Path, source, today=None, log=print):
    today = today or date.today()
    if not workbook.exists():
        log(f"Workbook not found – creating a new one at {workbook.name}")
        bp.build_workbook().save(workbook)
    wb = load_workbook(workbook)
    for name in ("Prices", "Transactions", "CommSec Import", "Dividends", "Portfolio", "Summary"):
        if name not in wb.sheetnames:
            raise SystemExit(f"'{name}' sheet missing – is this the right workbook?")
    p, t, im, d = wb["Prices"], wb["Transactions"], wb["CommSec Import"], wb["Dividends"]
    if p["H4"].value != "Company tax rate":
        raise SystemExit("This workbook is an older version without the automatic-refresh columns.\n"
                         "Rename it, then run the refresh again to create a fresh workbook.")
    warnings = []
    first_run = str(p["H11"].value or "").strip().lower() == "yes"

    # --- 1. remove example data on first run
    if first_run:
        for r in range(bp.TX_FIRST, bp.TX_LAST + 1):
            if str(t.cell(r, 8).value or "").startswith("Example"):
                for c in (1, 2, 3, 4, 5, 6, 8):
                    t.cell(r, c).value = None
        log("Removed example data.")

    # --- 2. CommSec import
    files, raw = load_exports(exports)
    log(f"CommSec exports: {len(files)} file(s), {len(raw)} unique row(s).")
    if not files:
        warnings.append(f"No CSV files in '{exports.name}' – only trades on the Transactions sheet are used.")
    if len(raw) > bp.IMP_ROWS:
        raise SystemExit(f"{len(raw)} CommSec rows but the sheet holds {bp.IMP_ROWS}.")
    for r in range(bp.IM_FIRST, bp.IM_LAST + 1):
        for c in range(1, 7):
            im.cell(r, c).value = None
    for i, row in enumerate(raw):
        r = bp.IM_FIRST + i
        for c, k in enumerate(("date", "reference", "details", "debit", "credit", "balance"), 1):
            im.cell(r, c).value = row[k] if row[k] not in ("",) else None

    # --- 3. all trades (CommSec + manual Transactions sheet)
    trades = []  # (date, ticker, signed units)
    for row in raw:
        tr = parse_trade(row["details"])
        if tr:
            side, units, ticker, _ = tr
            trades.append((row["date"], ticker, units if side == "Buy" else -units))
        elif row["details"][:2].upper() in ("B ", "S "):
            warnings.append(f"Couldn't read CommSec line: {row['details']!r}")
    for r in range(bp.TX_FIRST, bp.TX_LAST + 1):
        tk, typ, units, dt = t.cell(r, 2).value, t.cell(r, 3).value, t.cell(r, 4).value, t.cell(r, 1).value
        if tk and typ in ("Buy", "Sell") and units:
            try:
                trades.append((to_date(dt), str(tk).strip().upper(), float(units) * (1 if typ == "Buy" else -1)))
            except (TypeError, ValueError):
                warnings.append(f"Transactions row {r}: check the date/units")
    log(f"Trades found: {len(trades)}.")
    tickers_traded = []
    for _, tk, _ in sorted(trades):
        if tk not in tickers_traded:
            tickers_traded.append(tk)

    # --- 4. Prices list: keep existing rows, add new tickers, drop examples you don't own
    prow = []
    for r in range(bp.P_FIRST, bp.P_FIRST + bp.N_TICKERS):
        vals = [p.cell(r, c).value for c in range(1, 7)]
        if vals[0]:
            vals[0] = str(vals[0]).strip().upper()
            if first_run and vals[0] not in tickers_traded:
                continue
            if first_run:
                vals[4] = None  # example franking % – user should confirm their own
            prow.append(vals)
    have = {v[0] for v in prow}
    for tk in tickers_traded:
        if tk not in have:
            prow.append([tk, None, None, None, None, None])
    if len(prow) > bp.N_TICKERS:
        warnings.append(f"{len(prow)} shares but the workbook holds {bp.N_TICKERS}; "
                        f"dropped: {', '.join(v[0] for v in prow[bp.N_TICKERS:])}")
        prow = prow[:bp.N_TICKERS]

    # --- 5. prices + names
    for v in prow:
        code = v[5] or f"{v[0]}.AX"
        try:
            v[2], v[3] = source.price(code)
            log(f"  {v[0]:<6} price ${v[2]:,.3f} ({v[3]:%d %b %Y})")
        except Exception as e:  # keep the old price
            warnings.append(f"{v[0]}: no price from Yahoo ({code}): {e} – kept the old price")
        if not v[1]:
            try:
                v[1] = source.name(code)
            except Exception:
                pass
        if v[4] is None:
            warnings.append(f"{v[0]}: set its Franking % on the Prices sheet (franking credits are $0 until you do)")
    for i in range(bp.N_TICKERS):
        r = bp.P_FIRST + i
        vals = prow[i] if i < len(prow) else [None] * 6
        for c in range(6):
            p.cell(r, c + 1).value = vals[c]

    # --- 6. dividends
    kept, auto = [], []
    for r in range(bp.TX_FIRST, bp.TX_LAST + 1):
        vals = [d.cell(r, c).value for c in range(1, 9)]
        src = str(vals[6] or "").strip()
        if not any(vals[:4]) or src == "Auto" or (first_run and src == "Example"):
            continue
        vals[6] = src or "Manual"
        kept.append(vals)
    kept_keys = {(str(v[1]).upper(), to_date(v[0])) for v in kept if v[0] and v[1]}
    for v in prow:
        tk = v[0]
        my = [(dt, u) for dt, k, u in trades if k == tk]
        if not my:
            continue
        first = min(dt for dt, _ in my)
        try:
            divs = source.dividends(v[5] or f"{tk}.AX")
        except Exception as e:
            warnings.append(f"{tk}: couldn't download dividends: {e}")
            continue
        n = 0
        for ex, amt in divs:
            if ex < first - timedelta(days=7) or ex > today or (tk, ex) in kept_keys:
                continue
            units = sum(u for dt, u in my if entitled(dt, ex))
            if units > 0.0001:
                auto.append([ex, tk, round(units, 4), amt, None, None, "Auto", "Yahoo Finance – ex-dividend date"])
                n += 1
        log(f"  {tk:<6} {n} dividend(s) while held")
    rows = sorted(kept + auto, key=lambda v: (to_date(v[0]) or date.min, str(v[1])))
    if len(rows) > bp.TX_ROWS:
        raise SystemExit(f"{len(rows)} dividend rows but the sheet holds {bp.TX_ROWS}.")
    for i in range(bp.TX_ROWS):
        r = bp.TX_FIRST + i
        vals = rows[i] if i < len(rows) else [None] * 8
        for c in (1, 2, 3, 4, 7, 8):
            d.cell(r, c).value = vals[c - 1]
        d.cell(r, 5).value = f'=IF(OR(B{r}="",C{r}=""),"",C{r}*D{r})'
        f_old = vals[5]
        typed = f_old not in (None, "") and not str(f_old).startswith("=")
        d.cell(r, 6).value = f_old if (typed and vals[6] == "Manual") else bp.franking_formula(r)

    # --- 7. finish
    p["H8"].value = datetime.now().replace(microsecond=0)
    p["H11"].value = "No"
    bp.add_charts(wb, len(prow))
    wb.calculation.fullCalcOnLoad = True
    try:
        wb.save(workbook)
    except PermissionError:
        raise SystemExit("Couldn't save – the workbook is open in Excel. Close it and run the refresh again.")
    log(f"\nSaved {workbook.name}: {len(prow)} shares, {len(trades)} trades, "
        f"{len(auto)} auto + {len(kept)} manual dividend rows.")
    if warnings:
        log("\nPlease check:")
        for w in warnings:
            log(f"  - {w}")
    return {"shares": len(prow), "trades": len(trades), "auto": len(auto), "kept": len(kept), "warnings": warnings}


def main():
    EXPORTS.mkdir(exist_ok=True)
    print("Refreshing share portfolio...\n")
    refresh(WORKBOOK, EXPORTS, YahooSource())
    if "--no-open" not in sys.argv and sys.platform.startswith("win"):
        import os
        os.startfile(WORKBOOK)  # opens in Excel


if __name__ == "__main__":
    main()
