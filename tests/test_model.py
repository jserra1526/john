from pathlib import Path

import pandas as pd
import pytest

from milk_opt import DataError, load_data, optimise

SAMPLE = Path(__file__).parents[1] / "data" / "sample"


def write_tiny(directory: Path, **overrides) -> Path:
    """One region, one plant, butter + SMP, two months; easy to check by hand.

    Milk is 40 kg fat and 35 kg protein per tonne. Butter takes 800 kg fat per
    tonne and SMP 350 kg protein per tonne, so 1,000 t of milk makes exactly
    50 t butter and 100 t SMP.
    """
    months = ["2026-01", "2026-02"]
    tables = {
        "components": pd.DataFrame({"component": ["fat", "protein"], "surplus_value_per_kg": [0, 0]}),
        "supply": pd.DataFrame({
            "region": "R", "month": months, "volume_t": 1000, "milk_price_per_t": 300,
            "spot_price_per_t": 0, "spot_max_t": 0, "fat": 40, "protein": 35}),
        "transport": pd.DataFrame({"region": ["R"], "plant": ["P"], "cost_per_t": [10]}),
        "plant_intake": pd.DataFrame({"plant": "P", "month": months, "intake_capacity_t": 5000}),
        "lines": pd.DataFrame({"plant": "P", "line": ["Butter", "Butter", "Dryer", "Dryer"],
                               "month": months * 2, "hours_available": 1000}),
        "line_rates": pd.DataFrame({"plant": "P", "line": ["Butter", "Dryer"],
                                    "product": ["Butter", "SMP"], "rate_t_per_hr": [1.0, 1.0]}),
        "products": pd.DataFrame({
            "product": ["Butter", "SMP"], "processing_cost_per_t": [100, 100],
            "holding_cost_per_t_month": [5, 5], "storage_capacity_t": [1000, 1000],
            "initial_inventory_t": [0, 0], "min_closing_inventory_t": [0, 0],
            "shelf_life_months": [6, 6], "fat": [800, 0], "protein": [0, 350]}),
        "demand": pd.DataFrame({
            "product": ["Butter", "Butter", "SMP", "SMP"], "month": months * 2,
            "min_t": 0, "max_t": 1000, "price_per_t": [6000, 6000, 3000, 3000],
            "shortfall_penalty_per_t": 0}),
    }
    for name, df in overrides.items():
        tables[name] = df
    for name, df in tables.items():
        df.to_csv(directory / f"{name}.csv", index=False)
    return directory


def test_tiny_model_matches_hand_calculation(tmp_path):
    sol = optimise(load_data(write_tiny(tmp_path)))
    made = sol.production.groupby("product")["made_t"].sum()
    assert made["Butter"] == pytest.approx(100)
    assert made["SMP"] == pytest.approx(200)
    # Per month: 50*6000 + 100*3000 revenue, 1000*(300+10) milk+freight, 150*100 processing.
    assert sol.objective == pytest.approx(2 * (300_000 + 300_000 - 310_000 - 15_000))


def test_binding_line_reports_shadow_price(tmp_path):
    lines = pd.DataFrame({"plant": "P", "line": ["Butter", "Butter", "Dryer", "Dryer"],
                          "month": ["2026-01", "2026-02"] * 2, "hours_available": [25, 25, 1000, 1000]})
    supply = pd.DataFrame({"region": "R", "month": ["2026-01", "2026-02"], "volume_t": 1000,
                           "milk_price_per_t": 300, "spot_price_per_t": 200, "spot_max_t": 2000,
                           "fat": 40, "protein": 35})
    sol = optimise(load_data(write_tiny(tmp_path, lines=lines, supply=supply)))
    # Butter line can only make 25 t/month (fat from 500 t of milk); the rest of the fat
    # goes to surplus, so another butter-line hour is worth money.
    assert sol.line_use.query("line == 'Butter'")["utilisation"].tolist() == pytest.approx([1, 1])
    assert sol.line_use.query("line == 'Butter'")["shadow_price_per_hr"].min() > 0


def test_zero_shelf_life_prevents_stockholding(tmp_path):
    products = pd.DataFrame({
        "product": ["Butter", "SMP"], "processing_cost_per_t": [100, 100],
        "holding_cost_per_t_month": [0, 0], "storage_capacity_t": [1000, 1000],
        "initial_inventory_t": [0, 0], "min_closing_inventory_t": [0, 0],
        "shelf_life_months": [0, 6], "fat": [800, 0], "protein": [0, 350]})
    demand = pd.DataFrame({
        "product": ["Butter", "Butter", "SMP", "SMP"], "month": ["2026-01", "2026-02"] * 2,
        "min_t": 0, "max_t": [10, 1000, 1000, 1000], "price_per_t": [6000, 9000, 3000, 3000],
        "shortfall_penalty_per_t": 0})
    sol = optimise(load_data(write_tiny(tmp_path, products=products, demand=demand)))
    butter = sol.sales.query("product == 'Butter'")
    assert butter["closing_inv_t"].max() == pytest.approx(0, abs=1e-6)
    assert butter.query("month == '2026-01'")["sold_t"].item() == pytest.approx(10)


@pytest.fixture(scope="module")
def sample():
    data = load_data(SAMPLE)
    return data, optimise(data)


def test_sample_solves_without_dumping_or_shortfall(sample):
    _, sol = sample
    assert sol.status == "Optimal"
    assert sol.spot["dumped_t"].sum() == pytest.approx(0, abs=1e-6)
    assert sol.sales["shortfall_t"].sum() == pytest.approx(0, abs=1e-6)


def test_sample_respects_physical_limits(sample):
    data, sol = sample
    tol = 1e-4
    assert (sol.line_use["hours_used"] <= sol.line_use["hours_available"] + tol).all()
    assert (sol.intake["milk_in_t"] <= sol.intake["intake_capacity_t"] + tol).all()

    # All milk is accounted for.
    supplied = data.supply.set_index(["region", "month"])["volume_t"]
    used = (sol.flows.groupby(["region", "month"])["milk_t"].sum()
            .add(sol.spot.set_index(["region", "month"])["spot_sold_t"], fill_value=0))
    pd.testing.assert_series_equal(used.sort_index(), supplied.sort_index(), check_names=False, atol=tol)

    # Components in products never exceed components in the milk delivered.
    supply = data.supply.set_index(["region", "month"])
    recipes = data.products.set_index("product")
    for comp in data.component_names:
        milk_in = sol.flows.assign(kg=lambda f: f["milk_t"] * [supply.at[(r, t), comp]
                                                               for r, t in zip(f["region"], f["month"])])
        into = milk_in.groupby(["plant", "month"])["kg"].sum()
        out = sol.production.assign(kg=lambda f: f["made_t"] * f["product"].map(recipes[comp]))
        out = out.groupby(["plant", "month"])["kg"].sum()
        assert (out.reindex(into.index, fill_value=0) <= into + 1e-3).all()

    # Sales sit within demand bounds.
    demand = data.demand.set_index(["product", "month"])
    sales = sol.sales.set_index(["product", "month"])
    assert (sales["sold_t"] <= demand["max_t"] + tol).all()


def test_milk_marginal_value_matches_finite_difference(sample):
    data, sol = sample
    region, month, delta = "North", "2027-05", 50.0
    data.supply.loc[(data.supply.region == region) & (data.supply.month == month), "volume_t"] += delta
    bumped = optimise(data)
    data.supply.loc[(data.supply.region == region) & (data.supply.month == month), "volume_t"] -= delta
    dual = sol.milk_value.query("region == @region and month == @month")["marginal_value_per_t"].item()
    assert (bumped.objective - sol.objective) / delta == pytest.approx(dual, rel=1e-4, abs=1e-3)


def test_unknown_plant_is_rejected(tmp_path):
    transport = pd.DataFrame({"region": ["R"], "plant": ["Nowhere"], "cost_per_t": [10]})
    with pytest.raises(DataError, match="transport.plant"):
        load_data(write_tiny(tmp_path, transport=transport))
