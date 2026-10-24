"""Load and validate the Excel input workbook."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

COMPONENTS = ("fat", "protein", "la")  # la = lactose + ash; water is the remainder


class InputError(ValueError):
    """Raised when the input workbook is inconsistent."""


@dataclass
class ModelData:
    settings: dict
    weeks: list[int]
    zones: pd.DataFrame  # index: zone
    supply: pd.DataFrame  # index: (zone, week)
    factories: pd.DataFrame  # index: factory
    routes: pd.DataFrame  # index: (zone, factory)
    streams: pd.DataFrame  # index: stream
    products: pd.DataFrame  # index: product
    product_inputs: pd.DataFrame  # index: (product, component)
    byproducts: pd.DataFrame  # index: (product, component)
    plants: pd.DataFrame  # index: plant
    processes: pd.DataFrame  # index: (plant, product)
    plant_hours: pd.DataFrame  # index: (plant, week)
    market: pd.DataFrame  # index: (product, week)
    spot: pd.DataFrame  # index: week

    def product_streams(self, product: str) -> list[str]:
        return [s.strip() for s in str(self.products.at[product, "input_streams"]).split(";") if s.strip()]

    def max_kg_per_kL_milk(self, product: str) -> float | None:
        """Optional cap on output per kL of milk taken in by the factory (e.g. lactoferrin)."""
        if "max_kg_per_kL_milk" not in self.products.columns:
            return None
        v = self.products.at[product, "max_kg_per_kL_milk"]
        return None if pd.isna(v) else float(v)

    def is_spec_product(self, product: str) -> bool:
        """Spec products have a total dairy solids figure and flexible component ranges."""
        return pd.notna(self.products.at[product, "dairy_solids_kg_per_t"])


def _sheet(xl: pd.ExcelFile, name: str, index: list[str] | str | None = None) -> pd.DataFrame:
    if name not in xl.sheet_names:
        raise InputError(f"Missing sheet '{name}'")
    df = xl.parse(name)
    if index is not None:
        df = df.set_index(index).sort_index()
        if not df.index.is_unique:
            raise InputError(f"Sheet '{name}' has duplicate keys")
    return df


def load_workbook(path: str | Path) -> ModelData:
    xl = pd.ExcelFile(path)
    settings_df = _sheet(xl, "Settings")
    data = ModelData(
        settings=dict(zip(settings_df["setting"], settings_df["value"])),
        weeks=sorted(_sheet(xl, "Weeks")["week"].astype(int).tolist()),
        zones=_sheet(xl, "Zones", "zone"),
        supply=_sheet(xl, "Supply", ["zone", "week"]),
        factories=_sheet(xl, "Factories", "factory"),
        routes=_sheet(xl, "Routes", ["zone", "factory"]),
        streams=_sheet(xl, "Streams", "stream"),
        products=_sheet(xl, "Products", "product"),
        product_inputs=_sheet(xl, "Product_Inputs", ["product", "component"]),
        byproducts=_sheet(xl, "Byproducts", ["product", "component"]),
        plants=_sheet(xl, "Plants", "plant"),
        processes=_sheet(xl, "Processes", ["plant", "product"]),
        plant_hours=_sheet(xl, "Plant_Hours", ["plant", "week"]),
        market=_sheet(xl, "Market", ["product", "week"]),
        spot=_sheet(xl, "Spot", "week"),
    )
    validate(data)
    return data


def validate(d: ModelData) -> None:
    """Check cross-sheet references so mistakes surface as clear messages, not solver errors."""
    errors: list[str] = []

    def check_refs(values, valid, what):
        bad = sorted(set(values) - set(valid))
        if bad:
            errors.append(f"{what}: unknown {bad}")

    for key in ("milk_density_kg_per_L", "spot_fat_pct", "spot_protein_pct", "spot_la_pct"):
        if key not in d.settings:
            errors.append(f"Settings: missing '{key}'")

    check_refs(d.supply.index.get_level_values("zone"), d.zones.index, "Supply zones")
    check_refs(d.routes.index.get_level_values("zone"), d.zones.index, "Routes zones")
    check_refs(d.routes.index.get_level_values("factory"), d.factories.index, "Routes factories")
    check_refs(d.plants["factory"], d.factories.index, "Plants factories")
    check_refs(d.processes.index.get_level_values("plant"), d.plants.index, "Processes plants")
    check_refs(d.processes.index.get_level_values("product"), d.products.index, "Processes products")
    check_refs(d.product_inputs.index.get_level_values("product"), d.products.index, "Product_Inputs products")
    check_refs(d.product_inputs.index.get_level_values("component"), COMPONENTS, "Product_Inputs components")
    check_refs(d.byproducts.index.get_level_values("product"), d.products.index, "Byproducts products")
    check_refs(d.market.index.get_level_values("product"), d.products.index, "Market products")
    check_refs(d.plant_hours.index.get_level_values("plant"), d.plants.index, "Plant_Hours plants")

    for p in d.products.index:
        check_refs(d.product_streams(p), d.streams.index, f"Products '{p}' input_streams")
        bp = d.products.at[p, "byproduct_stream"]
        if pd.notna(bp):
            check_refs([bp], d.streams.index, f"Products '{p}' byproduct_stream")
        for c in COMPONENTS:
            if (p, c) not in d.product_inputs.index:
                errors.append(f"Product_Inputs: missing row for ({p}, {c})")
            elif d.product_inputs.at[(p, c), "min_kg_per_t"] > d.product_inputs.at[(p, c), "max_kg_per_t"]:
                errors.append(f"Product_Inputs: min > max for ({p}, {c})")
        if (p, d.weeks[0]) not in d.market.index:
            errors.append(f"Market: no rows for product '{p}'")

    for z in d.zones.index:
        missing = [w for w in d.weeks if (z, w) not in d.supply.index]
        if missing:
            errors.append(f"Supply: zone '{z}' missing weeks {missing[:5]}...")
    missing = [w for w in d.weeks if w not in d.spot.index]
    if missing:
        errors.append(f"Spot: missing weeks {missing[:5]}...")

    if errors:
        raise InputError("Input workbook problems:\n  - " + "\n  - ".join(errors))
