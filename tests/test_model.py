import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from milkopt import InputError, MilkModel, load_workbook

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sample_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "sample.xlsx"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_sample_data.py"), str(path)], check=True)
    return path


@pytest.fixture(scope="module")
def data(sample_path):
    return load_workbook(sample_path)


@pytest.fixture(scope="module")
def results(data):
    res = MilkModel(data).solve()
    assert res.status == "Optimal"
    return res


def test_all_milk_is_collected(data, results):
    sent = results.tables["Milk_Allocation"].groupby(["zone", "week"])["kL"].sum()
    spot = results.tables["Spot_Milk"].query("direction == 'sell'").set_index(["location", "week"])["kL"]
    spot.index.names = ["zone", "week"]
    total = sent.add(spot, fill_value=0)
    expected = data.supply["volume_kL"]
    assert (total.reindex(expected.index) - expected).abs().max() < 1e-3


def test_plant_hours_respected(results):
    u = results.tables["Plant_Utilisation"]
    assert (u["hours_used"] <= u["hours_available"] + 1e-6).all()


def test_spec_products_within_spec(data, results):
    prod = results.tables["Production"].query("tonnes > 1e-3")
    for p in ["SMP", "WMP", "MPC85", "IF_BASE"]:
        rows = prod[prod["product"] == p]
        for c in ["fat", "protein", "la"]:
            lo = data.product_inputs.at[(p, c), "min_kg_per_t"]
            hi = data.product_inputs.at[(p, c), "max_kg_per_t"]
            assert rows[f"{c}_kg_per_t"].between(lo - 1e-4, hi + 1e-4).all(), (p, c)
        solids = rows[["fat_kg_per_t", "protein_kg_per_t", "la_kg_per_t"]].sum(axis=1)
        assert (solids - data.products.at[p, "dairy_solids_kg_per_t"]).abs().max() < 1e-4


def test_protein_standardisation_floor(results):
    prod = results.tables["Production"].query("tonnes > 1e-3 and product in ['SMP', 'WMP']")
    ratio = prod["protein_kg_per_t"] / (prod["protein_kg_per_t"] + prod["la_kg_per_t"])
    assert (ratio >= 0.34 - 1e-6).all()


def test_stock_balance_and_closing(data, results):
    s = results.tables["Sales_Stock"]
    made = results.tables["Production"].groupby(["product", "week"])["tonnes"].sum()
    for p, g in s.groupby("product"):
        g = g.sort_values("week")
        prev = data.products.at[p, "opening_stock_t"]
        for r in g.itertuples():
            assert abs(prev + made.get((p, r.week), 0) - r.sales_t - r.closing_stock_t) < 1e-4
            prev = r.closing_stock_t
        assert prev >= data.products.at[p, "closing_stock_min_t"] - 1e-6


def test_milk_has_positive_marginal_value(results):
    mv = results.tables["Marginal_Values"]["value_of_extra_kL_milk"]
    assert mv.between(0, 2000).all()


def test_higher_price_makes_more(data):
    base = MilkModel(data).solve().tables["Production"]
    data.market.loc[pd.IndexSlice["PERM", :], "price_per_t"] = 6000
    try:
        res = MilkModel(data).solve()
    finally:
        data.market.loc[pd.IndexSlice["PERM", :], "price_per_t"] = 1250
    perm = lambda t: t.query("product == 'PERM'")["tonnes"].sum()
    assert perm(res.tables["Production"]) > perm(base) + 100


def test_bad_reference_is_reported(sample_path, tmp_path):
    sheets = pd.read_excel(sample_path, sheet_name=None)
    sheets["Processes"].loc[0, "product"] = "NOT_A_PRODUCT"
    bad = tmp_path / "bad.xlsx"
    with pd.ExcelWriter(bad) as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
    with pytest.raises(InputError, match="NOT_A_PRODUCT"):
        load_workbook(bad)


def test_mpc_only_on_one_dryer(results):
    prod = results.tables["Production"].query("product == 'MPC85' and tonnes > 1e-6")
    assert set(prod["plant"]) <= {"BOR_D3"}


def test_lactoferrin_limited_by_milk_intake(data, results):
    cap = data.max_kg_per_kL_milk("LACTOFERRIN")
    lf = results.tables["Production"].query("product == 'LACTOFERRIN'").groupby(["factory", "week"])["tonnes"].sum()
    assert lf.sum() > 0
    milk = results.tables["Milk_Allocation"].groupby(["factory", "week"])["kL"].sum()
    spot = results.tables["Spot_Milk"].query("direction == 'buy'").set_index(["location", "week"])["kL"]
    spot.index.names = ["factory", "week"]
    intake = milk.add(spot, fill_value=0)
    assert (lf * 1000 <= cap * intake.reindex(lf.index) + 1e-6).all()


def test_transfers_within_composition_and_limits(data, results):
    tr = results.tables["Transfers"].query("kL > 1e-3")
    assert len(tr) > 0
    for r in tr.itertuples():
        tt = data.transfer_types.loc[r.transfer_type]
        for c in ["fat", "protein", "la"]:
            v = getattr(r, f"{c}_kg_per_kL")
            assert tt[f"{c}_min_kg_per_kL"] - 1e-4 <= v <= tt[f"{c}_max_kg_per_kL"] + 1e-4
        assert r.kL <= data.transfer_routes.at[(r.transfer_type, r.from_factory, r.to_factory), "max_kL_per_week"] + 1e-6


def test_workbook_without_transfer_sheets_still_runs(sample_path, tmp_path):
    sheets = pd.read_excel(sample_path, sheet_name=None)
    old = tmp_path / "no_transfers.xlsx"
    with pd.ExcelWriter(old) as xw:
        for name, df in sheets.items():
            if not name.startswith("Transfer"):
                df.to_excel(xw, sheet_name=name, index=False)
    res = MilkModel(load_workbook(old)).solve()
    assert res.status == "Optimal"
    assert res.tables["Transfers"].empty
