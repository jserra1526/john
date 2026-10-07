"""Generate the illustrative dataset in data/sample/.

The numbers are made up but chosen to be plausible: a seasonal (spring-peak)
milk curve, three supply regions, three plants with different product lines,
and five products with flat-ish demand so that inventory is needed to carry
peak milk into the shoulder months.

Run:  python scripts/make_sample_data.py [output_dir]
"""

import sys
from pathlib import Path

import pandas as pd

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parents[1] / "data" / "sample")
MONTHS = [f"2026-{m:02d}" for m in range(7, 13)] + [f"2027-{m:02d}" for m in range(1, 7)]

# Share of peak-month milk, Jul..Jun (spring peak in Oct, winter trough in Jun).
SEASON = [0.30, 0.65, 0.90, 1.00, 0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.25, 0.10]
# Fat and protein (kg per tonne of milk) drift up as the season progresses.
FAT = [44, 42, 41, 41, 42, 43, 44, 45, 47, 49, 51, 52]
PROTEIN = [35, 34, 33, 33, 34, 35, 36, 37, 38, 39, 40, 40]

REGIONS = {"North": 95_000, "Central": 75_000, "South": 60_000}  # peak-month tonnes

components = pd.DataFrame([
    # Surplus fat goes to low-value cream sale, surplus protein to stockfeed.
    {"component": "fat", "surplus_value_per_kg": 2.0},
    {"component": "protein", "surplus_value_per_kg": 0.5},
])

supply = pd.DataFrame([
    {
        "region": r, "month": m, "volume_t": round(peak * s),
        "milk_price_per_t": 470, "spot_price_per_t": 400, "spot_max_t": 8_000,
        "fat": f, "protein": pr,
    }
    for r, peak in REGIONS.items()
    for m, s, f, pr in zip(MONTHS, SEASON, FAT, PROTEIN)
])

transport = pd.DataFrame([
    ("North", "Northgate", 12), ("North", "Midvale", 28),
    ("Central", "Northgate", 26), ("Central", "Midvale", 10), ("Central", "Southport", 30),
    ("South", "Midvale", 27), ("South", "Southport", 11),
], columns=["region", "plant", "cost_per_t"])

PLANT_INTAKE = {"Northgate": 110_000, "Midvale": 80_000, "Southport": 65_000}
# Winter maintenance shutdowns: Northgate in Jun, Southport in Jul.
SHUT = {("Northgate", "2027-06"), ("Southport", "2026-07")}
plant_intake = pd.DataFrame([
    {"plant": p, "month": m, "intake_capacity_t": 0 if (p, m) in SHUT else cap}
    for p, cap in PLANT_INTAKE.items() for m in MONTHS
])

# plant, line, hours/month, {product: tonnes/hr}
LINES = [
    ("Northgate", "Dryer1", 680, {"WMP": 12.0, "SMP": 13.0}),
    ("Northgate", "Butter1", 650, {"Butter": 4.0}),
    ("Midvale", "Cheese1", 680, {"Cheese": 4.5}),
    ("Midvale", "Butter2", 600, {"Butter": 2.5}),
    ("Midvale", "Cream1", 600, {"Cream": 6.0}),
    ("Southport", "Dryer2", 680, {"WMP": 9.0, "SMP": 10.0}),
    ("Southport", "Cheese2", 680, {"Cheese": 2.5}),
]
lines = pd.DataFrame([
    {"plant": p, "line": l, "month": m, "hours_available": 0 if (p, m) in SHUT else h}
    for p, l, h, _ in LINES for m in MONTHS
])
line_rates = pd.DataFrame([
    {"plant": p, "line": l, "product": k, "rate_t_per_hr": rate}
    for p, l, _, rates in LINES for k, rate in rates.items()
])

# Recipe columns are kg of each component consumed per tonne of product,
# including process losses (e.g. whey protein lost in cheesemaking).
products = pd.DataFrame([
    ("Butter", 380, 15, 12_000, 1_500, 1_500, 9, 815, 7),
    ("Cheese", 650, 20, 15_000, 3_000, 3_000, 9, 340, 330),
    ("WMP", 420, 8, 30_000, 2_000, 2_000, 12, 265, 250),
    ("SMP", 400, 8, 25_000, 2_000, 2_000, 12, 8, 340),
    ("Cream", 120, 30, 600, 0, 0, 0, 400, 20),
], columns=["product", "processing_cost_per_t", "holding_cost_per_t_month", "storage_capacity_t",
            "initial_inventory_t", "min_closing_inventory_t", "shelf_life_months", "fat", "protein"])

# product: (monthly min contract t, monthly max market t, base price $/t, shortfall penalty $/t)
DEMAND = {
    "Butter": (1_200, 2_600, 6_600, 1_500),
    "Cheese": (1_500, 3_600, 5_400, 1_500),
    "WMP": (2_500, 7_000, 3_800, 800),
    "SMP": (1_500, 5_000, 3_000, 800),
    "Cream": (300, 1_200, 3_100, 500),
}
# Mild price seasonality: prices soften at peak and firm in the off-season.
PRICE_FACTOR = [1.03, 1.01, 0.98, 0.96, 0.96, 0.98, 1.00, 1.01, 1.02, 1.03, 1.04, 1.05]
demand = pd.DataFrame([
    {"product": k, "month": m, "min_t": lo, "max_t": hi,
     "price_per_t": round(price * pf), "shortfall_penalty_per_t": pen}
    for k, (lo, hi, price, pen) in DEMAND.items()
    for m, pf in zip(MONTHS, PRICE_FACTOR)
])

OUT.mkdir(parents=True, exist_ok=True)
for name, df in {
    "components": components, "supply": supply, "transport": transport,
    "plant_intake": plant_intake, "lines": lines, "line_rates": line_rates,
    "products": products, "demand": demand,
}.items():
    df.to_csv(OUT / f"{name}.csv", index=False)
print(f"wrote sample data to {OUT}")
