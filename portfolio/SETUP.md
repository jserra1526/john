# Share Portfolio Tracker – Windows setup

One-off setup takes about 5 minutes. After that, refreshing is a double-click.

## 1. Install Python (once)

1. Go to **python.org/downloads** and click the yellow **Download Python** button.
2. Run the installer. On the first screen, **tick "Add python.exe to PATH"**, then click **Install Now**.
3. When it finishes, click Close.

## 2. Put the tool in a folder

Unzip `portfolio-tool.zip` somewhere permanent, e.g. `Documents\Share Portfolio`. You should see:

| File / folder | What it is |
|---|---|
| `share-portfolio-tracker.xlsx` | Your workbook |
| `Refresh Portfolio.bat` | Double-click this to refresh |
| `CommSec Exports\` | Put your CommSec CSV files here |
| `refresh.py`, `build_portfolio.py`, `requirements.txt` | The tool itself – leave these alone |

## 3. Export your trades from CommSec

1. Log in to CommSec → **Portfolio → Accounts → Transactions**.
2. Choose a date range starting **before your first ever purchase**, and download as **CSV**.
3. Save the file into the `CommSec Exports` folder. Next time, just export the last few months and drop it in too – duplicate rows across files are ignored.

## 4. Refresh

1. **Close the workbook in Excel** (Windows can't save over an open file).
2. Double-click **Refresh Portfolio.bat**. The first run installs two add-ons (`openpyxl`, `yfinance`) and takes a minute or so.
3. A window shows progress and anything you need to check, then the workbook opens.

If Windows shows *"Windows protected your PC"*, click **More info → Run anyway** (it's a plain text file you can open in Notepad to read).

## 5. After the first refresh – a few checks

- **Prices sheet → Franking %**: set each share's usual franking (e.g. 100% for most big banks and miners; ETFs vary – check a recent distribution statement). Franking credits stay $0 until you do. Then refresh again.
- **Dividends sheet**: compare a few rows against your dividend statements.
  - A dividend is wrong (e.g. different units)? Fix the row and change **Source** to `Manual` – the refresh will keep your version and not re-add its own.
  - A payment is missing (special dividend, capital return, unlisted fund)? Add a row with Source `Manual`.
- **DRP (dividend reinvestment)**: DRP shares come from the share registry, not CommSec, so they aren't in your export. Add each DRP allotment on the **Transactions** sheet as a `Buy` with brokerage 0, so later dividends include those shares.

## What's automated and what isn't

| Automated | Still yours to do |
|---|---|
| Importing every CommSec buy and sell, with brokerage | Dropping in a new CommSec export now and then |
| Current prices and company names | Setting Franking % once per share |
| Dividend history and how many units you held at each ex-date | Adding DRP allotments and anything not listed on Yahoo |
| Cost, value, gains/losses, capital and dividend returns | |

## Where the data comes from

Prices and dividend history come from **Yahoo Finance** (codes like `CBA.AX`), which carries ASX market data. The ASX itself doesn't offer a free dividend feed. Yahoo doesn't publish franking, which is why you set Franking % per share. If a share has a different Yahoo code, put it in the **Yahoo Code** column on the Prices sheet.

Dividend rows created automatically are dated on the **ex-dividend date**, not the payment date, so "Dividends by Year" on the Summary sheet is grouped by ex-date.

## Troubleshooting

| Message | Fix |
|---|---|
| `Python is not installed` | Re-run the Python installer and tick **Add python.exe to PATH**. |
| `Couldn't save – the workbook is open in Excel` | Close Excel and double-click Refresh again. |
| `no price from Yahoo` | Yahoo was briefly unavailable, or the code is different (fill in Yahoo Code). The old price is kept. |
| `older version without the automatic-refresh columns` | Rename your old workbook; the refresh creates a fresh one. |
| A trade is missing | Check the `CommSec Import` sheet's Status column. |
