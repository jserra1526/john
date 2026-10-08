# LCNRV Inventory – Power BI model

A Power BI model that values month-end inventory at the **lower of cost and net realisable value (LCNRV)**. For each month, SKU and location it shows the volume, unit cost, total cost, NRV, carrying value and write-down.

It's saved as a Power BI Project (`.pbip`). The model is in TMDL and the report is in PBIR, so every file is plain text and works with git.

## Getting started

1. Copy `data/LCNRV_Data.xlsx` somewhere on your machine, e.g. `C:\LCNRV\data\LCNRV_Data.xlsx` (that's the default path).
2. Open `LCNRV Inventory.pbip` in Power BI Desktop. You need a recent version; the PBIR report format must be on in older builds: *File › Options › Preview features › Power BI Project (.pbip) save option* and *Store reports using enhanced metadata format (PBIR)*.
3. If you saved the workbook somewhere else, go to *Transform data › Edit parameters* and set **DataWorkbook** to its full path.
4. Click **Refresh**.

To use your own numbers, replace the rows in the workbook's three Excel tables. Keep the table names and column headers the same.

| Excel table | Grain | Columns |
|---|---|---|
| `tblInventory` | month × SKU × location | `MonthEnd`, `SKU`, `Location`, `Quantity`, `UnitCost` (COGS / weighted-average cost per unit) |
| `tblPrices` | month × SKU | `MonthEnd`, `SKU`, `SellingPrice`, `CostToComplete` (per unit), `SellingCostPct` (of price) |
| `tblProducts` | SKU | `SKU`, `Description`, `Category` |

`MonthEnd` can be any date in the month; the model moves it to the month end.

## How the LCNRV test works

The test runs **line by line** (month × SKU × location) in Power Query. Running it on aggregated totals would let gains on one item hide losses on another.

```
NRV per unit      = SellingPrice × (1 − SellingCostPct) − CostToComplete
LCNRV unit value  = MIN(UnitCost, MAX(NRV per unit, 0))     -- UnitCost if no price exists
Total Cost        = Quantity × UnitCost
LCNRV Value       = Quantity × LCNRV unit value
Write-down        = Total Cost − LCNRV Value
```

If a line has no selling price for the month, it stays at cost. The **Lines Missing Price** measure counts these lines so you can follow them up.

## Measures (table `Inventory`)

Inventory is a balance, not a flow. So when several months are in context (a year subtotal, say), every measure shows the **closing balance at the last month**. Months are never added together.

| Folder | Measure | Meaning |
|---|---|---|
| 1. Volume & Cost | **Volume** | Units on hand |
| | **Unit Cost** | Weighted-average cost per unit |
| | **Total Cost** | Inventory at cost |
| 2. NRV | **Selling Price**, **NRV per Unit** | Weighted averages over priced units |
| | **Total NRV** | Quantity × NRV per unit |
| 3. LCNRV | **LCNRV Value**, **LCNRV Unit Value** | Carrying value after the test |
| | **Write-down**, **Write-down %** | Provision balance and % of cost |
| | **Write-down Prior Month**, **Write-down Movement** | Roll-forward: positive = charge to COGS, negative = release |
| 4. Checks | **Lines Written Down**, **Lines Missing Price** | Exception counts |

## Report pages

- **LCNRV Summary** – Month, Category and Location slicers; KPI cards; a cost vs LCNRV chart by month; and a matrix of SKUs × months showing Volume, Unit Cost, Total Cost, NRV per Unit, LCNRV Value and Write-down.
- **LCNRV Detail** – the line-level test for each SKU × location × month.
- **Write-down Roll-forward** – opening provision → movement → closing provision for each month, plus the exception counts.

## Checking the numbers

`python tools/expected_results.py` recalculates the same logic in pandas. The monthly totals it prints should match the Roll-forward page exactly. With the sample data, Sep 2026 should show:
Volume 9,914 · Total Cost $360,426 · LCNRV Value $299,462 · Write-down $60,964 · 2 lines missing price.

## Accounting notes / things to adapt

- **IFRS (IAS 2)** lets you reverse a write-down when NRV recovers, and this model does that automatically: each month is re-tested from scratch. **US GAAP (ASC 330)** doesn't allow reversals within a fiscal year, so a written-down cost becomes the new cost basis. To follow that, feed the written-down cost back in as `UnitCost`.
- NRV has a floor of zero, so the write-down never goes above cost. If you also need to provide for onerous commitments, that has to be modelled separately.
- If you'd rather calculate the selling price from actual sales (revenue ÷ units sold), build `tblPrices` from your sales data. The model only needs one price per month × SKU.

## Repo layout

```
LCNRV Inventory.pbip              open this in Power BI Desktop
LCNRV Inventory.SemanticModel/    TMDL model (tables, measures, Power Query)
LCNRV Inventory.Report/           PBIR report pages and visuals
data/LCNRV_Data.xlsx              sample data / input template
tools/make_sample_data.py         regenerates the sample workbook
tools/build_report.py             regenerates the report definition
tools/expected_results.py         pandas reconciliation of the model logic
```
