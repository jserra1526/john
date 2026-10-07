"""Load and validate the CSV input data for the milk optimisation model.

All inputs live in one directory. See README.md for the full schema; in short:

    components.csv   component, surplus_value_per_kg
    supply.csv       region, month, volume_t, milk_price_per_t, spot_price_per_t,
                     spot_max_t, <one kg-per-tonne column per component>
    transport.csv    region, plant, cost_per_t
    plant_intake.csv plant, month, intake_capacity_t
    lines.csv        plant, line, month, hours_available
    line_rates.csv   plant, line, product, rate_t_per_hr
    products.csv     product, processing_cost_per_t, holding_cost_per_t_month,
                     storage_capacity_t, initial_inventory_t,
                     min_closing_inventory_t, shelf_life_months,
                     <one kg-per-tonne recipe column per component>
    demand.csv       product, month, min_t, max_t, price_per_t,
                     shortfall_penalty_per_t
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "components": ["component", "surplus_value_per_kg"],
    "supply": ["region", "month", "volume_t", "milk_price_per_t", "spot_price_per_t", "spot_max_t"],
    "transport": ["region", "plant", "cost_per_t"],
    "plant_intake": ["plant", "month", "intake_capacity_t"],
    "lines": ["plant", "line", "month", "hours_available"],
    "line_rates": ["plant", "line", "product", "rate_t_per_hr"],
    "products": [
        "product",
        "processing_cost_per_t",
        "holding_cost_per_t_month",
        "storage_capacity_t",
        "initial_inventory_t",
        "min_closing_inventory_t",
        "shelf_life_months",
    ],
    "demand": ["product", "month", "min_t", "max_t", "price_per_t", "shortfall_penalty_per_t"],
}


class DataError(ValueError):
    """Raised when the input data is missing or inconsistent."""


@dataclass
class ModelData:
    components: pd.DataFrame
    supply: pd.DataFrame
    transport: pd.DataFrame
    plant_intake: pd.DataFrame
    lines: pd.DataFrame
    line_rates: pd.DataFrame
    products: pd.DataFrame
    demand: pd.DataFrame

    @property
    def component_names(self) -> list[str]:
        return list(self.components["component"])

    @property
    def months(self) -> list[str]:
        # Months are YYYY-MM strings, so lexical order is chronological order.
        return sorted(self.supply["month"].unique())

    @property
    def regions(self) -> list[str]:
        return sorted(self.supply["region"].unique())

    @property
    def plants(self) -> list[str]:
        return sorted(self.plant_intake["plant"].unique())

    @property
    def product_names(self) -> list[str]:
        return list(self.products["product"])


def load_data(directory: str | Path) -> ModelData:
    directory = Path(directory)
    frames = {}
    for name, columns in REQUIRED_COLUMNS.items():
        path = directory / f"{name}.csv"
        if not path.exists():
            raise DataError(f"missing input file: {path}")
        df = pd.read_csv(path, dtype={"month": str})
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise DataError(f"{path.name} is missing columns: {missing}")
        # Numeric data as float: PuLP does not accept numpy integer scalars as coefficients.
        numeric = df.select_dtypes("number").columns
        df[numeric] = df[numeric].astype(float)
        frames[name] = df
    data = ModelData(**frames)
    validate(data)
    return data


def validate(data: ModelData) -> None:
    comps = data.component_names
    for name in ("supply", "products"):
        missing = [c for c in comps if c not in getattr(data, name).columns]
        if missing:
            raise DataError(f"{name}.csv needs a column per component; missing {missing}")

    months = set(data.months)
    plants = set(data.plants)
    regions = set(data.regions)
    products = set(data.product_names)

    def check_subset(label, values, allowed):
        unknown = set(values) - allowed
        if unknown:
            raise DataError(f"{label} references unknown values: {sorted(unknown)}")

    check_subset("transport.region", data.transport["region"], regions)
    check_subset("transport.plant", data.transport["plant"], plants)
    check_subset("lines.plant", data.lines["plant"], plants)
    check_subset("lines.month", data.lines["month"], months)
    check_subset("plant_intake.month", data.plant_intake["month"], months)
    check_subset("line_rates.product", data.line_rates["product"], products)
    check_subset("demand.product", data.demand["product"], products)
    check_subset("demand.month", data.demand["month"], months)

    known_lines = set(zip(data.lines["plant"], data.lines["line"]))
    rate_lines = set(zip(data.line_rates["plant"], data.line_rates["line"]))
    check_subset("line_rates (plant, line)", rate_lines, known_lines)

    if (data.line_rates["rate_t_per_hr"] <= 0).any():
        raise DataError("line_rates.rate_t_per_hr must be positive")
    if (data.demand["min_t"] > data.demand["max_t"]).any():
        raise DataError("demand.min_t must not exceed demand.max_t")
    for name, df, keys in (
        ("supply", data.supply, ["region", "month"]),
        ("demand", data.demand, ["product", "month"]),
        ("plant_intake", data.plant_intake, ["plant", "month"]),
        ("lines", data.lines, ["plant", "line", "month"]),
    ):
        if df.duplicated(keys).any():
            raise DataError(f"{name}.csv has duplicate rows for {keys}")
