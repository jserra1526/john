"""Recompute the model's LCNRV logic in pandas, to reconcile against Power BI.

Usage: python tools/expected_results.py [data/LCNRV_Data.xlsx]
Prints month-end totals that should match the 'Write-down Roll-forward' page.
"""
import sys

import pandas as pd

path = sys.argv[1] if len(sys.argv) > 1 else "data/LCNRV_Data.xlsx"
inv = pd.read_excel(path, sheet_name="Inventory")
px = pd.read_excel(path, sheet_name="Prices")
for df in (inv, px):
    df["MonthEnd"] = pd.to_datetime(df["MonthEnd"]) + pd.offsets.MonthEnd(0)
px = px.fillna({"CostToComplete": 0, "SellingCostPct": 0}).drop_duplicates(["MonthEnd", "SKU"])
px["NRVPerUnit"] = px.SellingPrice * (1 - px.SellingCostPct) - px.CostToComplete

df = inv.merge(px[["MonthEnd", "SKU", "NRVPerUnit"]], on=["MonthEnd", "SKU"], how="left")
has_price = df.NRVPerUnit.notna()
df["LCNRVUnitValue"] = df.UnitCost.where(~has_price, df[["UnitCost"]].join(df.NRVPerUnit.clip(lower=0)).min(axis=1))
df["TotalCost"] = df.Quantity * df.UnitCost
df["LCNRVValue"] = df.Quantity * df.LCNRVUnitValue
df["WriteDown"] = df.TotalCost - df.LCNRVValue
df["MissingPrice"] = ~has_price

out = df.groupby("MonthEnd").agg(Volume=("Quantity", "sum"), TotalCost=("TotalCost", "sum"),
                                  LCNRVValue=("LCNRVValue", "sum"), WriteDown=("WriteDown", "sum"),
                                  LinesWrittenDown=("WriteDown", lambda s: int((s > 0).sum())),
                                  LinesMissingPrice=("MissingPrice", "sum"))
out["Movement"] = out.WriteDown.diff().fillna(out.WriteDown)
out["WriteDownPct"] = out.WriteDown / out.TotalCost
pd.set_option("display.width", 200)
print(out.round({"TotalCost": 0, "LCNRVValue": 0, "WriteDown": 0, "Movement": 0, "WriteDownPct": 4}).to_string())
