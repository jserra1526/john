"""Write solution tables to CSV and print a console summary."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .model import Solution

TABLES = ["flows", "spot", "production", "surplus", "sales", "line_use", "intake", "milk_value"]


def write_outputs(sol: Solution, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        getattr(sol, name).to_csv(directory / f"{name}.csv", index=False)
    pd.Series(sol.pnl, name="value").rename_axis("item").to_csv(directory / "pnl.csv")
    return directory


def summary(sol: Solution) -> str:
    out = [f"Status: {sol.status}", "", "P&L ($)"]
    for item, value in sol.pnl.items():
        out.append(f"  {item:<26}{value:>16,.0f}")

    out += ["", "Production by product and month (t)"]
    if not sol.production.empty:
        prod = sol.production.pivot_table(index="product", columns="month", values="made_t",
                                          aggfunc="sum", fill_value=0)
        out.append(prod.round(0).astype(int).to_string())

    sales = sol.sales
    short = sales[sales["shortfall_t"] > 1e-6]
    out += ["", "Contract shortfalls (t)"]
    out.append(short[["product", "month", "shortfall_t"]].round(0).to_string(index=False)
               if not short.empty else "  none")

    spot = sol.spot.groupby("region")[["spot_sold_t", "dumped_t"]].sum()
    out += ["", "Milk sold on spot / dumped (t)", spot.round(0).to_string()]

    lu = sol.line_use.pivot_table(index=["plant", "line"], columns="month", values="utilisation")
    out += ["", "Line utilisation (%)", (lu * 100).round(0).astype(int).to_string()]

    iu = sol.intake.pivot_table(index="plant", columns="month", values="utilisation")
    out += ["", "Plant milk intake utilisation (%)", (iu * 100).round(0).astype(int).to_string()]

    mv = sol.milk_value.pivot(index="region", columns="month", values="marginal_value_per_t")
    out += ["", "Marginal value of one more tonne of milk ($/t, net of milk price)",
            mv.round(0).astype(int).to_string()]
    return "\n".join(out)
