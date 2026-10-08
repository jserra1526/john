# Sales Report — Power BI Desktop project

A ready-to-open Power BI report saved in the **Power BI Project (`.pbip`)** format,
with a star-schema semantic model and four report pages, built on the sample
bike-shop sales data in [`data/`](data/): actuals from January 2025 to September 2026,
plus four FY2026 plan versions (Budget, Q1 Forecast, Q2 Forecast, Latest Estimate).

## Open it in Power BI Desktop

1. Clone or download this repository to a Windows machine, for example to
   `C:\PowerBI\SalesReport\`.
2. In Power BI Desktop, turn on **File → Options and settings → Options →
   Preview features → Power BI Project (.pbip) save option** and
   **Store reports using enhanced metadata format (PBIR)** if your version
   still lists them as previews (restart Desktop afterwards).
3. Double-click **`SalesReport.pbip`** (or *File → Open* and pick it).
4. Point the report at the CSV files: **Transform data → Edit parameters →
   `DataFolder`** and enter the full path of the `data` folder **with a
   trailing backslash**, e.g. `C:\PowerBI\SalesReport\data\`.
   (If you cloned to exactly `C:\PowerBI\SalesReport\`, the default already works.)
5. Click **Refresh**. All visuals fill in.

To share it as a single file, use *File → Save as* and choose `.pbix`.

## What's inside

### Semantic model (`SalesReport.SemanticModel/`, TMDL)

| Table | Source | Notes |
|---|---|---|
| `Sales` (fact) | `data/Sales.csv` — ~5,000 order lines, Jan 2025 – Sep 2026 | Actuals and their measures |
| `Plan` (fact) | `data/Plan.csv` — units and sales by month × product × region × version | Plan measures and variances |
| `Products` | `data/Products.csv` — 20 products in 4 categories | Unit price and cost |
| `Customers` | `data/Customers.csv` — 80 customers | Segment, country |
| `Regions` | `data/Regions.csv` | Shared by actuals (via Customers) and plan |
| `Calendar` | Generated in Power Query | Date table; `Period Type` = Actual / Forecast |
| `Scenario` | Defined in Power Query | Budget, Q1 Forecast, Q2 Forecast, Latest Estimate |
| `Variance Bridge` | Defined in Power Query | Steps for the price/volume waterfall |

**Plan versions** (all for FY2026):

| Version | Actual months | Forecast months |
|---|---|---|
| Budget | — | Jan–Dec (prior-year volume +12%, prior-year price +3%) |
| Q1 Forecast | Jan–Mar | Apr–Dec |
| Q2 Forecast | Jan–Jun | Jul–Dec |
| Latest Estimate | Jan–Sep | Oct–Dec |

Actual measures: **Total Sales**, **Total Cost**, **Gross Profit**, **Profit Margin %**,
**Orders**, **Units Sold**, **Avg Order Value**, **Avg Selling Price**, **Sales PY**, **Sales YoY %**.

Version measures: **Budget Sales**, **Q1 Forecast Sales**, **Q2 Forecast Sales**,
**Latest Estimate Sales**, **LE vs Budget**, **LE vs Budget %**.

**Price / volume variance** (Actual vs the version picked in the *Compare to* slicer,
Budget by default, over the months that have actuals), worked out product by product:

- **Volume Variance** = (actual units − plan units) × plan price
- **Price Variance** = (actual price − plan price) × actual units
- Volume + Price = **Sales Variance** (actual sales − plan sales), exactly.

Prices are net of discounts. A product with no plan is all volume variance.
Because a forecast version contains actuals for its closed months, Actual vs
Latest Estimate is zero year-to-date; compare to Budget, Q1 or Q2 to see a variance.

### Report (`SalesReport.Report/`, PBIR)

- **Sales Overview** — KPI cards (sales, profit, margin, orders, YoY growth),
  monthly sales vs. prior year, sales by customer segment, sales and profit by
  category, sales by country; Year and Region slicers.
- **Price & Volume Variance** — *Compare to* slicer (Budget / Q1 / Q2 / LE);
  cards for actual, comparison, total, volume and price variance; a waterfall
  bridge from the comparison version to actual; monthly volume vs. price
  variance; and a variance matrix by category and product. Filtered to FY2026.
- **Budget & Forecasts** — full-year totals for each version, LE vs Budget,
  monthly actual vs. every version, Budget vs LE by region, and a version
  matrix by category and product. Filtered to FY2026.
- **Products & Customers** — product performance table, customers ranked by
  sales, region × year matrix, quarterly sales by year; Category and Year slicers.

A custom colour theme lives in `StaticResources/RegisteredResources/SalesTheme.json`.

## Using your own data

Replace the CSVs in `data/` with your own files using the same column headers
and hit **Refresh**. For plan data, `Plan.csv` needs one row per version, month
(first day of the month), product and region, with `Units` and `Sales`; the
`Scenario` values must match the version names above (or edit the `Scenario`
table's list in Power Query to rename them). To change the structure, edit the model and visuals in
Power BI Desktop and save — the `.pbip` format keeps everything as readable
text files that diff cleanly in git.

`tools/generate_project.py` is the script that produced the sample data and
project files; rerun it (`python tools/generate_project.py .`) to rebuild from
scratch.
