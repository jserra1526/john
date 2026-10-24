"""Generate the made-up sample input workbook for the milk optimiser.

All numbers are invented but intended to be roughly realistic for a
seasonal temperate milk pool (2026/27 season, July-June). Zone, state and
factory names are generic code names.

Usage:
    python scripts/make_sample_data.py [output.xlsx]
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

WEEKS = list(range(1, 53))
SEASON_START = date(2026, 6, 29)  # Monday of the week containing 1 July
RNG = np.random.default_rng(42)


def seasonal(week: int, peak_week: float, amplitude: float) -> float:
    """Cosine curve centred on 1.0 that peaks at `peak_week`."""
    return 1.0 + amplitude * np.cos(2 * np.pi * (week - peak_week) / 52)


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
settings = pd.DataFrame(
    [
        ("season", "2026/27", "Label only"),
        ("milk_density_kg_per_L", 1.03, "Converts litres to kg"),
        ("freight_per_kL_km", 0.15, "Tanker cost $ per kL per one-way km incl. empty return (used to calculate Routes.freight_per_kL)"),
        ("farmgate_fat_per_kg", 6.20, "Farmgate milk price $/kg butterfat (reporting only - all milk is collected)"),
        ("farmgate_protein_per_kg", 13.70, "Farmgate milk price $/kg protein (reporting only)"),
        ("spot_fat_pct", 4.00, "Assumed composition of spot milk bought"),
        ("spot_protein_pct", 3.30, "Assumed composition of spot milk bought"),
        ("spot_la_pct", 5.60, "Assumed composition of spot milk bought"),
    ],
    columns=["setting", "value", "description"],
)

weeks = pd.DataFrame(
    {
        "week": WEEKS,
        "week_start": [SEASON_START + timedelta(weeks=w - 1) for w in WEEKS],
    }
)
weeks["month"] = [d.strftime("%b") for d in weeks["week_start"]]

# --------------------------------------------------------------------------
# Supply zones and weekly supply
# --------------------------------------------------------------------------
# Typical strongly seasonal monthly supply shape (1.0 = average week): low in winter,
# steep rise to an October peak, slow decline through summer and autumn.
BASE_MONTHLY_INDEX = {
    "Jul": 0.68, "Aug": 0.95, "Sep": 1.28, "Oct": 1.45, "Nov": 1.38, "Dec": 1.20,
    "Jan": 1.04, "Feb": 0.92, "Mar": 0.86, "Apr": 0.80, "May": 0.72, "Jun": 0.66,
}

# Annual supply (confirmed by state): State A 500 ML (split across zones 1-3), State B 40 ML, State C 100 ML.
# zone: (name, state, annual ML, seasonality vs base curve (1 = same, 0 = flat), base fat %, base protein %,
#        spot sell max kL/wk)
ZONES = {
    "Z1": ("Zone 1", "State A", 230, 1.00, 4.30, 3.45, 5000),
    "Z2": ("Zone 2", "State A", 140, 0.95, 4.35, 3.50, 4000),
    "Z3": ("Zone 3", "State A", 130, 0.80, 4.05, 3.35, 3000),
    "Z4": ("Zone 4", "State B", 40, 0.55, 4.25, 3.45, 1500),
    "Z5": ("Zone 5", "State C", 100, 0.75, 4.15, 3.40, 2500),
}

zones = pd.DataFrame(
    [(z, v[0], v[1], v[2], v[6]) for z, v in ZONES.items()],
    columns=["zone", "name", "state", "annual_supply_ML", "spot_sell_max_kL_per_week"],
)

# Weekly base index: monthly value for each week, smoothed with a circular 3-week average
base = np.array([BASE_MONTHLY_INDEX[m] for m in weeks["month"]])
base = (np.roll(base, 1) + base + np.roll(base, -1)) / 3
base = base / base.mean()

supply_rows = []
for z, (_, _, annual_ml, strength, fat, prot, _) in ZONES.items():
    shape = 1 + strength * (base - 1)
    for i, w in enumerate(WEEKS):
        vol = annual_ml * 1000 / 52 * shape[i] * RNG.normal(1.0, 0.015)
        # Components rise in late lactation (autumn, ~week 44) and dip in the spring flush
        comp = np.cos(2 * np.pi * (w - 44) / 52)
        supply_rows.append(
            (z, w, round(vol), round(fat + 0.35 * comp, 3), round(prot + 0.25 * comp, 3), round(5.55 - 0.10 * comp, 3))
        )
supply = pd.DataFrame(supply_rows, columns=["zone", "week", "volume_kL", "fat_pct", "protein_pct", "la_pct"])

# --------------------------------------------------------------------------
# Factories and tanker routes
# --------------------------------------------------------------------------
factories = pd.DataFrame(
    [
        ("ATL", "Atlas", "State A", 24000, 1500),
        ("BOR", "Boreas", "State A", 32000, 1500),
        ("CYG", "Cygnus", "State B", 14000, 1000),
    ],
    columns=["factory", "name", "state", "intake_kL_per_week", "spot_buy_max_kL_per_week"],
)

# Made-up one-way road km. Missing pairs are not allowed routes.
DISTANCES = {
    ("Z1", "BOR"): 40, ("Z1", "ATL"): 310, ("Z1", "CYG"): 780,
    ("Z2", "BOR"): 340, ("Z2", "ATL"): 280, ("Z2", "CYG"): 440,
    ("Z3", "ATL"): 40, ("Z3", "BOR"): 350, ("Z3", "CYG"): 500,
    ("Z4", "CYG"): 30, ("Z4", "ATL"): 540,
    ("Z5", "BOR"): 220, ("Z5", "ATL"): 500,
}
freight_rate = 0.15
routes = pd.DataFrame(
    [(z, f, km, round(km * freight_rate, 2)) for (z, f), km in DISTANCES.items()],
    columns=["zone", "factory", "distance_km", "freight_per_kL"],
)

# --------------------------------------------------------------------------
# Streams (component pools at each factory)
# --------------------------------------------------------------------------
streams = pd.DataFrame(
    [
        ("MILK", "Whole milk pool - freely separable/standardisable (cream, skim, UF retentate/permeate). High cost: dumping milk solids is a last resort", -5.00),
        ("WHEY", "Sweet whey from cheese making", 0.02),
        ("ACID_WHEY", "Acid whey from cream cheese", -0.05),
    ],
    columns=["stream", "description", "disposal_value_per_kg"],
)

# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
# Fixed-recipe products: dairy_solids blank, min = max component use, may create a by-product stream.
# Spec products: dairy_solids given, component ranges, optional protein/SNF minimum (standardisation).
P = [
    # product, description, input_streams, dairy_solids_kg_per_t, protein_snf_min, byproduct_stream,
    # var_cost, purchased_ingredient_cost, opening, max_stock, holding_cost, shortfall_penalty
    ("WMP", "Whole milk powder", "MILK", 970, 0.34, None, 380, 0, 1500, 8000, 8, None),
    ("SMP", "Skim milk powder", "MILK", 965, 0.34, None, 380, 0, 1500, 8000, 8, None),
    ("MPC85", "Milk protein concentrate 85", "MILK", 955, None, None, 1200, 0, 0, 2000, 10, None),
    ("PERM", "Permeate powder", "MILK", 970, None, None, 300, 0, 0, 4000, 6, None),
    ("AWP", "Acid whey powder", "ACID_WHEY", 960, None, None, 350, 0, 0, 2000, 6, None),
    ("D40", "Demineralised whey powder 40%", "WHEY", 970, None, None, 450, 0, 0, 3000, 6, None),
    ("IF_BASE", "Infant formula base powder", "MILK", 525, None, None, 900, 3000, 0, 2000, 12, 20000),
    ("LACTOFERRIN", "Lactoferrin (ion-exchange extraction from skim)", "MILK", 960, None, None, 60000, 0, 0, 20, 100, None),
    ("BUTTER", "Butter", "MILK;WHEY", None, None, None, 450, 0, 800, 3000, 15, None),
    ("CHEDDAR", "Cheddar cheese", "MILK", None, None, "WHEY", 900, 0, 3000, 6000, 12, 15000),
    ("STRINGERS", "String cheese (mozzarella)", "MILK", None, None, "WHEY", 1800, 0, 0, 600, 15, 18000),
    ("PARMESAN", "Parmesan", "MILK", None, None, "WHEY", 1500, 0, 500, 2000, 10, 20000),
    ("CREAM_CHEESE", "Cream cheese", "MILK", None, None, "ACID_WHEY", 1100, 0, 0, 800, 15, 15000),
]
products = pd.DataFrame(
    P,
    columns=[
        "product", "description", "input_streams", "dairy_solids_kg_per_t", "protein_snf_min",
        "byproduct_stream", "var_cost_per_t", "purchased_ingredient_cost_per_t", "opening_stock_t",
        "max_stock_t", "holding_cost_per_t_week", "shortfall_penalty_per_t",
    ],
)
products["closing_stock_min_t"] = products["opening_stock_t"]
# Products extracted from milk in small amounts are limited by the milk the factory takes in.
# Lactoferrin: ~0.1 g/L in milk x ~50% recovery = 0.05 kg per kL of milk.
products["max_kg_per_kL_milk"] = products["product"].map({"LACTOFERRIN": 0.05})

# kg of each component drawn from the input stream(s) per tonne of product (min, max).
# Cheese recipes draw protein and lactose+ash in roughly the ratio found in milk (~9 t milk per t cheddar).
INPUTS = {
    "WMP": {"fat": (260, 285), "protein": (0, 300), "la": (0, 999)},
    "SMP": {"fat": (5, 12), "protein": (0, 400), "la": (0, 999)},
    "MPC85": {"fat": (10, 25), "protein": (810, 840), "la": (0, 999)},
    "PERM": {"fat": (0, 5), "protein": (30, 60), "la": (0, 999)},
    "AWP": {"fat": (0, 20), "protein": (100, 180), "la": (0, 999)},
    "D40": {"fat": (0, 15), "protein": (95, 140), "la": (0, 999)},
    "IF_BASE": {"fat": (100, 160), "protein": (110, 130), "la": (250, 350)},
    "LACTOFERRIN": {"fat": (0, 5), "protein": (920, 960), "la": (0, 40)},
    "BUTTER": {"fat": (820, 820), "protein": (7, 7), "la": (13, 13)},
    "CHEDDAR": {"fat": (360, 360), "protein": (310, 310), "la": (499, 499)},
    "STRINGERS": {"fat": (240, 240), "protein": (305, 305), "la": (491, 491)},
    "PARMESAN": {"fat": (300, 300), "protein": (440, 440), "la": (708, 708)},
    "CREAM_CHEESE": {"fat": (340, 340), "protein": (100, 100), "la": (161, 161)},
}
product_inputs = pd.DataFrame(
    [(p, c, lo, hi) for p, comps in INPUTS.items() for c, (lo, hi) in comps.items()],
    columns=["product", "component", "min_kg_per_t", "max_kg_per_t"],
)

# kg of each component returned to the by-product stream per tonne of product
BYPRODUCTS = {
    "CHEDDAR": {"fat": 20, "protein": 60, "la": 459},
    "STRINGERS": {"fat": 20, "protein": 55, "la": 441},
    "PARMESAN": {"fat": 20, "protein": 80, "la": 658},
    "CREAM_CHEESE": {"fat": 10, "protein": 30, "la": 111},
}
byproducts = pd.DataFrame(
    [(p, c, kg) for p, comps in BYPRODUCTS.items() for c, kg in comps.items()],
    columns=["product", "component", "kg_per_t"],
)

# --------------------------------------------------------------------------
# Plants, what they can make, and available hours
# --------------------------------------------------------------------------
plants = pd.DataFrame(
    [
        ("ATL_D1", "ATL", "Atlas dryer 1 - infant formula"),
        ("ATL_D2", "ATL", "Atlas dryer 2 - SMP/WMP/AWP/permeate"),
        ("ATL_D3", "ATL", "Atlas dryer 3 - infant formula/WMP/SMP"),
        ("ATL_CC", "ATL", "Atlas cream cheese plant"),
        ("ATL_LF", "ATL", "Atlas lactoferrin plant"),
        ("BOR_D1", "BOR", "Boreas dryer 1 - SMP/WMP/permeate"),
        ("BOR_D2", "BOR", "Boreas dryer 2 - SMP/WMP/permeate"),
        ("BOR_D3", "BOR", "Boreas dryer 3 - SMP/WMP/permeate/MPC (only MPC dryer)"),
        ("BOR_LF", "BOR", "Boreas lactoferrin plant"),
        ("BOR_BUT", "BOR", "Boreas butter plant"),
        ("CYG_CHD", "CYG", "Cygnus cheddar plant"),
        ("CYG_STR", "CYG", "Cygnus stringers plant"),
        ("CYG_PAR", "CYG", "Cygnus parmesan plant"),
        ("CYG_D40", "CYG", "Cygnus D40 whey dryer"),
        ("CYG_BUT", "CYG", "Cygnus butter plant"),
    ],
    columns=["plant", "factory", "description"],
)

RATES = {
    "ATL_D1": {"IF_BASE": 3.0},
    "ATL_D2": {"SMP": 7.0, "WMP": 7.0, "AWP": 4.0, "PERM": 5.0},
    "ATL_D3": {"IF_BASE": 3.5, "WMP": 8.0, "SMP": 8.0},
    "ATL_CC": {"CREAM_CHEESE": 2.0},
    "ATL_LF": {"LACTOFERRIN": 0.008},
    "BOR_D1": {"SMP": 12.0, "WMP": 12.0, "PERM": 7.0},
    "BOR_D2": {"SMP": 8.0, "WMP": 8.0, "PERM": 5.0},
    "BOR_D3": {"SMP": 5.0, "WMP": 5.0, "MPC85": 1.5, "PERM": 3.0},
    "BOR_LF": {"LACTOFERRIN": 0.008},
    "BOR_BUT": {"BUTTER": 8.0},
    "CYG_CHD": {"CHEDDAR": 6.0},
    "CYG_STR": {"STRINGERS": 1.2},
    "CYG_PAR": {"PARMESAN": 0.8},
    "CYG_D40": {"D40": 2.5},
    "CYG_BUT": {"BUTTER": 3.0},
}
processes = pd.DataFrame(
    [(pl, p, r) for pl, prods in RATES.items() for p, r in prods.items()],
    columns=["plant", "product", "rate_t_per_h"],
)

# Annual maintenance shutdowns in the low-milk autumn/winter (weeks with 0 hours)
SHUTDOWNS = {
    "BOR_D1": [44, 45], "BOR_D2": [46, 47], "BOR_D3": [48, 49],
    "ATL_D2": [48, 49], "ATL_D3": [44, 45], "ATL_D1": [50],
    "CYG_D40": [50, 51], "CYG_CHD": [49], "BOR_BUT": [47], "CYG_BUT": [48],
}
CHRISTMAS_WEEK = 26
hours_rows = []
for pl in plants["plant"]:
    is_dryer = "_D" in pl
    for w in WEEKS:
        h = 150 if is_dryer else 120
        if w == CHRISTMAS_WEEK and not is_dryer:
            h = 80
        if w in SHUTDOWNS.get(pl, []):
            h = 0
        hours_rows.append((pl, w, h))
plant_hours = pd.DataFrame(hours_rows, columns=["plant", "week", "hours"])

# --------------------------------------------------------------------------
# Markets: weekly price and sales limits (blank max = unlimited)
# --------------------------------------------------------------------------
# product: (base price $/t, price swing, swing phase week, min sales t/wk, max sales t/wk)
MARKET = {
    "WMP": (5900, 0.08, 20, 0, None),
    "SMP": (4600, 0.06, 30, 0, None),
    "MPC85": (13500, 0.04, 10, 0, 70),
    "PERM": (1250, 0.05, 40, 0, None),
    "AWP": (850, 0.0, 0, 0, None),
    "D40": (1700, 0.05, 30, 0, None),
    "IF_BASE": (13000, 0.0, 0, 200, 450),
    "LACTOFERRIN": (600000, 0.0, 0, 0, None),
    "BUTTER": (9500, 0.07, 25, 0, None),
    "CHEDDAR": (8200, 0.0, 0, 400, 800),
    "STRINGERS": (11000, 0.0, 0, 80, 160),
    "PARMESAN": (13500, 0.0, 0, 40, 100),
    "CREAM_CHEESE": (7800, 0.0, 0, 120, 250),
}
market = pd.DataFrame(
    [
        (p, w, round(price * seasonal(w, phase, swing)), mn, mx)
        for p, (price, swing, phase, mn, mx) in MARKET.items()
        for w in WEEKS
    ],
    columns=["product", "week", "price_per_t", "min_sales_t", "max_sales_t"],
)

# --------------------------------------------------------------------------
# Spot milk prices: cheap in the spring flush, dear in autumn
# --------------------------------------------------------------------------
spot = pd.DataFrame(
    [
        (w, round(700 * seasonal(w, 45, 0.2)), round(700 * seasonal(w, 45, 0.2) - 60))
        for w in WEEKS
    ],
    columns=["week", "buy_price_per_kL", "sell_price_per_kL"],
)

# --------------------------------------------------------------------------
# Transfers between sites: milk, cream and permeate
# --------------------------------------------------------------------------
# Composition ranges in kg per kL shipped. The range lets the optimiser standardise what it sends.
transfer_types = pd.DataFrame(
    [
        # type, description, source, dest, whole_milk, fat min/max, protein min/max, la min/max
        ("MILK", "Whole milk (standardised within a normal milk range)", "MILK", "MILK", 1, 38, 47, 31, 37, 55, 59),
        ("CREAM", "Cream 40% fat (~396 kg fat/kL at 0.99 kg/L)", "MILK", "MILK", 0, 390, 400, 18, 22, 30, 36),
        ("PERMEATE", "UF permeate concentrated to 18% solids (~193 kg solids/kL at 1.07 kg/L)", "MILK", "MILK", 0, 0, 1, 4, 8, 182, 190),
    ],
    columns=[
        "transfer_type", "description", "source_stream", "dest_stream", "whole_milk",
        "fat_min_kg_per_kL", "fat_max_kg_per_kL", "protein_min_kg_per_kL", "protein_max_kg_per_kL",
        "la_min_kg_per_kL", "la_max_kg_per_kL",
    ],
)

# Made-up one-way km between sites and weekly limits by transfer type
SITE_DISTANCES = {("ATL", "BOR"): 310, ("ATL", "CYG"): 540, ("BOR", "CYG"): 820}
TRANSFER_MAX = {"MILK": 3000, "CREAM": 500, "PERMEATE": 1000}
transfer_routes = pd.DataFrame(
    [
        (g, a, b, km, round(km * freight_rate, 2), TRANSFER_MAX[g])
        for g in TRANSFER_MAX
        for (x, y), km in SITE_DISTANCES.items()
        for a, b in ((x, y), (y, x))
    ],
    columns=["transfer_type", "from_factory", "to_factory", "distance_km", "cost_per_kL", "max_kL_per_week"],
)

# --------------------------------------------------------------------------
# Scale made-up capacities to the milk pool
# --------------------------------------------------------------------------
# The plant, intake, spot, sales and transfer figures above were first sized for a 2,500 ML pool.
# The confirmed pool is 640 ML, so scale them down together. Replace with real figures when available.
CAPACITY_SCALE = 640 / 2500


def _scale(df: pd.DataFrame, cols: list[str], decimals: int = 0) -> None:
    for c in cols:
        df[c] = (df[c] * CAPACITY_SCALE).round(decimals)
        if decimals == 0:
            df[c] = df[c].astype("Int64")


_scale(factories, ["intake_kL_per_week", "spot_buy_max_kL_per_week"])
_scale(zones, ["spot_sell_max_kL_per_week"])
_scale(processes, ["rate_t_per_h"], 4)
_scale(market, ["min_sales_t", "max_sales_t"])
_scale(products, ["opening_stock_t", "closing_stock_min_t", "max_stock_t"])
_scale(transfer_routes, ["max_kL_per_week"])

# --------------------------------------------------------------------------
# README sheet
# --------------------------------------------------------------------------
readme = pd.DataFrame(
    [
        ("Settings", "Global parameters (density, freight rate, farmgate price, spot milk composition)"),
        ("Weeks", "The 52 weekly buckets of the July-June season"),
        ("Zones", "Milk collection zones and limit on spot milk sold from each zone"),
        ("Supply", "Weekly milk volume (kL) and composition (% w/w) by zone"),
        ("Factories", "Factory intake capacity and limit on spot milk bought"),
        ("Routes", "Allowed tanker routes zone -> factory and freight $/kL"),
        ("Streams", "Component pools at each factory and value ($/kg) of disposing surplus solids"),
        ("Products", "Product master: input streams, recipe type, costs, stock limits, yield limit per kL of milk"),
        ("Product_Inputs", "kg fat/protein/lactose+ash drawn per tonne of product (min/max)"),
        ("Byproducts", "kg components returned to the by-product stream per tonne (e.g. whey)"),
        ("Plants", "Processing plants and the factory they belong to"),
        ("Processes", "Which products each plant can make and at what rate (t/h)"),
        ("Plant_Hours", "Available operating hours per plant per week (0 = shutdown)"),
        ("Market", "Weekly price, minimum (committed) and maximum sales per product"),
        ("Spot", "Weekly spot milk buy and sell prices ($/kL)"),
        ("Transfer_Types", "What can be moved between sites (milk, cream, permeate) and its kg/kL composition range"),
        ("Transfer_Routes", "Allowed site-to-site transfers, cost $/kL and weekly limit"),
        ("", ""),
        ("NOTE", "All data in this workbook is made up for demonstration purposes."),
    ],
    columns=["sheet", "contents"],
)


def main(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    sheets = {
        "README": readme, "Settings": settings, "Weeks": weeks, "Zones": zones, "Supply": supply,
        "Factories": factories, "Routes": routes, "Streams": streams, "Products": products,
        "Product_Inputs": product_inputs, "Byproducts": byproducts, "Plants": plants,
        "Processes": processes, "Plant_Hours": plant_hours, "Market": market, "Spot": spot,
        "Transfer_Types": transfer_types, "Transfer_Routes": transfer_routes,
    }
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 80)
            ws.freeze_panes = "A2"
    print(f"Wrote {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/sample_inputs.xlsx"))
