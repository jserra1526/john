"""Write results to Excel and print a console summary."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .model import Results


def write_excel(res: Results, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in res.tables.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(12, len(str(col[0].value)) + 2)
            ws.freeze_panes = "A2"


def print_summary(res: Results) -> None:
    print(f"Status: {res.status}")
    if not res.tables:
        return
    print("\nSeason P&L (AUD m)")
    for r in res.tables["Summary"].itertuples():
        print(f"  {r.item:<32}{r.AUD / 1e6:>10.1f}")

    milk = res.tables["Milk_Allocation"]
    print("\nMilk allocation (ML/season)")
    print((milk.pivot_table(index="zone", columns="factory", values="kL", aggfunc="sum", fill_value=0) / 1000)
          .round(0).to_string())
    spot = res.tables["Spot_Milk"].groupby("direction")["kL"].sum() / 1000
    print(f"\nSpot milk: sold {spot.get('sell', 0):.0f} ML, bought {spot.get('buy', 0):.0f} ML")

    tr = res.tables.get("Transfers")
    if tr is not None and tr["kL"].sum() > 1e-3:
        print("\nTransfers between sites (ML/season)")
        print((tr.pivot_table(index=["from_factory", "to_factory"], columns="transfer_type", values="kL",
                              aggfunc="sum", fill_value=0) / 1000).round(1).to_string())

    prod = res.tables["Production"]
    print("\nProduction (t/season)")
    print(prod.pivot_table(index="product", columns="factory", values="tonnes", aggfunc="sum", fill_value=0)
          .round(0).to_string())

    u = res.tables["Plant_Utilisation"]
    s = u.groupby("plant")[["hours_used", "hours_available"]].sum()
    s["utilisation_%"] = (100 * s["hours_used"] / s["hours_available"]).round(0)
    print("\nPlant utilisation (season)")
    print(s["utilisation_%"].to_string())

    short = res.tables["Sales_Stock"]["shortfall_t"].sum()
    if short > 1e-3:
        print(f"\nWARNING: {short:,.0f} t of committed sales could not be met")
