# Sales Report — Power BI Desktop project

A ready-to-open Power BI report saved in the **Power BI Project (`.pbip`)** format,
with a star-schema semantic model and two report pages, built on the sample
bike-shop sales data in [`data/`](data/).

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
| `Sales` (fact) | `data/Sales.csv` — ~6,000 order lines, 2024–2025 | Holds all measures |
| `Products` | `data/Products.csv` — 20 products in 4 categories | Unit price and cost |
| `Customers` | `data/Customers.csv` — 80 customers | Segment, region, country |
| `Calendar` | Generated in Power Query | Marked as the date table |

Relationships: `Sales` → `Products`, `Customers`, `Calendar` (many-to-one).

Measures: **Total Sales**, **Total Cost**, **Gross Profit**, **Profit Margin %**,
**Orders**, **Units Sold**, **Avg Order Value**, **Sales PY**, **Sales YoY %**.

### Report (`SalesReport.Report/`, PBIR)

- **Sales Overview** — KPI cards (sales, profit, margin, orders, YoY growth),
  monthly sales vs. prior year, sales by customer segment, sales and profit by
  category, sales by country; Year and Region slicers.
- **Products & Customers** — product performance table, customers ranked by
  sales, region × year matrix, quarterly sales by year; Category and Year slicers.

A custom colour theme lives in `StaticResources/RegisteredResources/SalesTheme.json`.

## Using your own data

Replace the CSVs in `data/` with your own files using the same column headers
and hit **Refresh**. To change the structure, edit the model and visuals in
Power BI Desktop and save — the `.pbip` format keeps everything as readable
text files that diff cleanly in git.

`tools/generate_project.py` is the script that produced the sample data and
project files; rerun it (`python tools/generate_project.py .`) to rebuild from
scratch.
