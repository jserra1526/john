"""Linear programme: allocate milk and plant capacity to maximise season profit.

See docs/design.md for the mathematical formulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import pulp

from .data import COMPONENTS, ModelData


@dataclass
class Results:
    status: str
    objective: float
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)


def _lim(value) -> float | None:
    """Excel blank -> no limit."""
    return None if pd.isna(value) else float(value)


class MilkModel:
    def __init__(self, data: ModelData):
        self.d = data
        self.prob = pulp.LpProblem("milk_allocation", pulp.LpMaximize)
        self._build()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        d, W = self.d, self.d.weeks
        kg_per_kL = float(d.settings["milk_density_kg_per_L"]) * 1000
        spot_pct = {c: float(d.settings[f"spot_{c}_pct"]) for c in COMPONENTS}
        procs = list(d.processes.index)  # (plant, product)
        plant_factory = d.plants["factory"].to_dict()
        V = pulp.LpVariable.dicts

        # --- decision variables (all >= 0) ---
        self.x = V("milk", [(z, f, w) for z, f in d.routes.index for w in W], lowBound=0)  # kL zone -> factory
        self.spot_sell = {
            (z, w): pulp.LpVariable(f"spot_sell_{z}_{w}", 0, _lim(d.zones.at[z, "spot_sell_max_kL_per_week"]))
            for z in d.zones.index for w in W
        }
        self.spot_buy = {
            (f, w): pulp.LpVariable(f"spot_buy_{f}_{w}", 0, _lim(d.factories.at[f, "spot_buy_max_kL_per_week"]))
            for f in d.factories.index for w in W
        }
        self.make = V("make", [(pl, p, w) for pl, p in procs for w in W], lowBound=0)  # t product
        self.draw = V(  # kg component drawn from a stream into a process
            "draw",
            [(pl, p, s, c, w) for pl, p in procs for s in d.product_streams(p) for c in COMPONENTS for w in W],
            lowBound=0,
        )
        pools = [(f, s) for f in d.factories.index for s in d.streams.index]
        self.dispose = V("dispose", [(f, s, c, w) for f, s in pools for c in COMPONENTS for w in W], lowBound=0)
        self.sell = {}
        self.short = {}
        for p in d.products.index:
            for w in W:
                m = d.market.loc[(p, w)]
                self.sell[p, w] = pulp.LpVariable(f"sell_{p}_{w}", 0, _lim(m["max_sales_t"]))
                if (_lim(m["min_sales_t"]) or 0) > 0:
                    self.short[p, w] = pulp.LpVariable(f"short_{p}_{w}", 0)
        self.inv = {
            (p, w): pulp.LpVariable(f"inv_{p}_{w}", 0, _lim(d.products.at[p, "max_stock_t"]))
            for p in d.products.index for w in W
        }

        prob = self.prob
        self.con_supply, self.con_hours, self.con_pool = {}, {}, {}

        # --- 1. all farm milk is collected: sent to a factory or sold spot ---
        for z in d.zones.index:
            for w in W:
                lhs = pulp.lpSum(self.x[z, f, w] for zz, f in d.routes.index if zz == z) + self.spot_sell[z, w]
                c = lhs == float(d.supply.at[(z, w), "volume_kL"])
                prob += c, f"supply_{z}_{w}"
                self.con_supply[z, w] = c

        # --- 2. factory intake capacity ---
        for f in d.factories.index:
            for w in W:
                prob += (
                    pulp.lpSum(self.x[z, ff, w] for z, ff in d.routes.index if ff == f) + self.spot_buy[f, w]
                    <= float(d.factories.at[f, "intake_kL_per_week"])
                ), f"intake_{f}_{w}"

        # --- 3. component balance for every stream pool at every factory ---
        for f, s in pools:
            fprocs = [(pl, p) for pl, p in procs if plant_factory[pl] == f]
            for c in COMPONENTS:
                for w in W:
                    inflow = []
                    if s == "MILK":
                        inflow += [
                            self.x[z, f, w] * kg_per_kL * float(d.supply.at[(z, w), f"{c}_pct"]) / 100
                            for z, ff in d.routes.index if ff == f
                        ]
                        inflow.append(self.spot_buy[f, w] * kg_per_kL * spot_pct[c] / 100)
                    inflow += [
                        self.make[pl, p, w] * float(d.byproducts.at[(p, c), "kg_per_t"])
                        for pl, p in fprocs
                        if d.products.at[p, "byproduct_stream"] == s and (p, c) in d.byproducts.index
                    ]
                    outflow = [self.draw[pl, p, s, c, w] for pl, p in fprocs if s in d.product_streams(p)]
                    con = pulp.lpSum(inflow) == pulp.lpSum(outflow) + self.dispose[f, s, c, w]
                    prob += con, f"pool_{f}_{s}_{c}_{w}"
                    self.con_pool[f, s, c, w] = con

        # --- 4. product recipes / specifications ---
        for pl, p in procs:
            spec = d.is_spec_product(p)
            psnf = _lim(d.products.at[p, "protein_snf_min"])
            for w in W:
                y = self.make[pl, p, w]
                used = {c: pulp.lpSum(self.draw[pl, p, s, c, w] for s in d.product_streams(p)) for c in COMPONENTS}
                tag = f"{pl}_{p}_{w}"
                for c in COMPONENTS:
                    lo = float(d.product_inputs.at[(p, c), "min_kg_per_t"])
                    hi = float(d.product_inputs.at[(p, c), "max_kg_per_t"])
                    if lo == hi:
                        prob += used[c] == lo * y, f"recipe_{c}_{tag}"
                    else:
                        prob += used[c] >= lo * y, f"spec_min_{c}_{tag}"
                        prob += used[c] <= hi * y, f"spec_max_{c}_{tag}"
                if spec:
                    solids = float(d.products.at[p, "dairy_solids_kg_per_t"])
                    prob += pulp.lpSum(used.values()) == solids * y, f"solids_{tag}"
                if psnf is not None:  # protein standardisation: protein >= x% of solids-non-fat
                    prob += used["protein"] >= psnf * (used["protein"] + used["la"]), f"psnf_{tag}"

        # --- 4b. extraction limits: output capped by milk taken in (e.g. lactoferrin kg per kL) ---
        for p in d.products.index:
            cap = d.max_kg_per_kL_milk(p)
            if cap is None:
                continue
            for f in d.factories.index:
                fprocs = [(pl, pp) for pl, pp in procs if pp == p and plant_factory[pl] == f]
                if not fprocs:
                    continue
                for w in W:
                    milk_in = pulp.lpSum(self.x[z, f, w] for z, ff in d.routes.index if ff == f) + self.spot_buy[f, w]
                    prob += (
                        pulp.lpSum(self.make[pl, p, w] for pl, _ in fprocs) * 1000 <= cap * milk_in
                    ), f"extract_{p}_{f}_{w}"

        # --- 5. plant hours ---
        for pl in d.plants.index:
            for w in W:
                hrs = float(d.plant_hours["hours"].get((pl, w), 0.0))
                c = pulp.lpSum(
                    self.make[pl, p, w] * (1.0 / float(d.processes.at[(pl, p), "rate_t_per_h"]))
                    for ppl, p in procs if ppl == pl
                ) <= hrs
                prob += c, f"hours_{pl}_{w}"
                self.con_hours[pl, w] = c

        # --- 6. inventory and sales ---
        for p in d.products.index:
            prev = float(d.products.at[p, "opening_stock_t"])
            for w in W:
                produced = pulp.lpSum(self.make[pl, pp, w] for pl, pp in procs if pp == p)
                prob += self.inv[p, w] == prev + produced - self.sell[p, w], f"stock_{p}_{w}"
                prev = self.inv[p, w]
                mn = _lim(d.market.at[(p, w), "min_sales_t"]) or 0
                if mn > 0:
                    prob += self.sell[p, w] + self.short[p, w] >= mn, f"minsales_{p}_{w}"
            closing = _lim(d.products.at[p, "closing_stock_min_t"]) or 0
            prob += self.inv[p, W[-1]] >= closing, f"closing_{p}"

        # --- objective: season contribution (farmgate milk cost is fixed and reported separately) ---
        revenue = pulp.lpSum(self.sell[p, w] * float(d.market.at[(p, w), "price_per_t"]) for p, w in self.sell)
        proc_cost = pulp.lpSum(
            self.make[pl, p, w]
            * (float(d.products.at[p, "var_cost_per_t"]) + float(d.products.at[p, "purchased_ingredient_cost_per_t"]))
            for pl, p in procs for w in W
        )
        freight = pulp.lpSum(
            self.x[z, f, w] * float(d.routes.at[(z, f), "freight_per_kL"]) for z, f in d.routes.index for w in W
        )
        spot = pulp.lpSum(
            self.spot_sell[z, w] * float(d.spot.at[w, "sell_price_per_kL"]) for z, w in self.spot_sell
        ) - pulp.lpSum(self.spot_buy[f, w] * float(d.spot.at[w, "buy_price_per_kL"]) for f, w in self.spot_buy)
        holding = pulp.lpSum(
            self.inv[p, w] * float(d.products.at[p, "holding_cost_per_t_week"]) for p, w in self.inv
        )
        disposal = pulp.lpSum(
            v * float(d.streams.at[s, "disposal_value_per_kg"]) for (f, s, c, w), v in self.dispose.items()
        )
        shortfall = pulp.lpSum(
            v * float(d.products.at[p, "shortfall_penalty_per_t"]) for (p, w), v in self.short.items()
        )
        self.terms = {
            "Product revenue": revenue,
            "Spot milk (net)": spot,
            "Disposal value": disposal,
            "Processing & ingredient cost": -proc_cost,
            "Tanker freight": -freight,
            "Stock holding cost": -holding,
            "Shortfall penalty": -shortfall,
        }
        prob += pulp.lpSum(self.terms.values())

    # ------------------------------------------------------------------ solve
    def solve(self, msg: bool = False, time_limit: float | None = None) -> Results:
        solver = pulp.HiGHS(msg=msg, timeLimit=time_limit)
        self.prob.solve(solver)
        status = pulp.LpStatus[self.prob.status]
        if status == "Optimal":
            self._load_duals()
        res = Results(status=status, objective=pulp.value(self.prob.objective) or 0.0)
        if status == "Optimal":
            res.tables = self._extract()
        return res

    def _load_duals(self) -> None:
        """PuLP's HiGHS interface only returns primal values; read the row duals directly.

        HiGHS rows are added in the order of prob.constraints, so they line up one-to-one.
        For a maximisation HiGHS reports duals with the opposite sign, so negate them to get
        pi = change in objective per unit increase of the constraint's right-hand side.
        """
        duals = self.prob.solverModel.getSolution().row_dual
        for con, dual in zip(self.prob.constraints.values(), duals):
            con.pi = -dual

    # ---------------------------------------------------------------- results
    def _extract(self) -> dict[str, pd.DataFrame]:
        d, W = self.d, self.d.weeks
        val = pulp.value
        kg_per_kL = float(d.settings["milk_density_kg_per_L"]) * 1000
        t: dict[str, pd.DataFrame] = {}

        # P&L
        milk_cost = sum(
            r.volume_kL * kg_per_kL / 100
            * (r.fat_pct * float(d.settings["farmgate_fat_per_kg"]) + r.protein_pct * float(d.settings["farmgate_protein_per_kg"]))
            for r in d.supply.itertuples()
        )
        rows = [(k, val(v) or 0.0) for k, v in self.terms.items()]
        contribution = sum(v for _, v in rows)
        rows += [("Contribution (objective)", contribution), ("Farmgate milk cost (fixed)", -milk_cost),
                 ("Profit after milk cost", contribution - milk_cost)]
        t["Summary"] = pd.DataFrame(rows, columns=["item", "AUD"])

        t["Milk_Allocation"] = pd.DataFrame(
            [(z, f, w, v.value(), v.value() * float(d.routes.at[(z, f), "freight_per_kL"]))
             for (z, f, w), v in self.x.items()],
            columns=["zone", "factory", "week", "kL", "freight_AUD"],
        )
        t["Spot_Milk"] = pd.concat([
            pd.DataFrame([("sell", z, w, v.value(), float(d.spot.at[w, "sell_price_per_kL"]))
                          for (z, w), v in self.spot_sell.items()], columns=["direction", "location", "week", "kL", "price_per_kL"]),
            pd.DataFrame([("buy", f, w, v.value(), float(d.spot.at[w, "buy_price_per_kL"]))
                          for (f, w), v in self.spot_buy.items()], columns=["direction", "location", "week", "kL", "price_per_kL"]),
        ])

        prod_rows = []
        for (pl, p, w), v in self.make.items():
            tonnes = v.value() or 0.0
            used = {c: sum(self.draw[pl, p, s, c, w].value() or 0.0 for s in d.product_streams(p)) for c in COMPONENTS}
            prod_rows.append((
                d.plants.at[pl, "factory"], pl, p, w, tonnes,
                tonnes / float(d.processes.at[(pl, p), "rate_t_per_h"]),
                *(used[c] / tonnes if tonnes > 1e-6 else None for c in COMPONENTS),
            ))
        t["Production"] = pd.DataFrame(
            prod_rows,
            columns=["factory", "plant", "product", "week", "tonnes", "hours",
                     "fat_kg_per_t", "protein_kg_per_t", "la_kg_per_t"],
        )

        util = t["Production"].groupby(["plant", "week"])["hours"].sum()
        t["Plant_Utilisation"] = pd.DataFrame(
            [(d.plants.at[pl, "factory"], pl, w, util.get((pl, w), 0.0),
              float(d.plant_hours["hours"].get((pl, w), 0.0)),
              self.con_hours[pl, w].pi)
             for pl in d.plants.index for w in W],
            columns=["factory", "plant", "week", "hours_used", "hours_available", "value_per_extra_hour"],
        )
        u = t["Plant_Utilisation"]
        u["utilisation"] = (u["hours_used"] / u["hours_available"]).where(u["hours_available"] > 0)

        t["Sales_Stock"] = pd.DataFrame(
            [(p, w, float(d.market.at[(p, w), "price_per_t"]), self.sell[p, w].value(),
              self.short[p, w].value() if (p, w) in self.short else 0.0, self.inv[p, w].value())
             for p in d.products.index for w in W],
            columns=["product", "week", "price_per_t", "sales_t", "shortfall_t", "closing_stock_t"],
        )

        t["Disposals"] = pd.DataFrame(
            [(f, s, c, w, v.value()) for (f, s, c, w), v in self.dispose.items() if (v.value() or 0) > 1e-3],
            columns=["factory", "stream", "component", "week", "kg"],
        )

        t["Marginal_Values"] = pd.DataFrame(
            [(z, w, self.con_supply[z, w].pi) for z in d.zones.index for w in W],
            columns=["zone", "week", "value_of_extra_kL_milk"],
        )
        t["Component_Values"] = pd.DataFrame(
            [(f, s, c, w, -self.con_pool[f, s, c, w].pi)
             for (f, s, c, w) in self.con_pool if s == "MILK"],
            columns=["factory", "stream", "component", "week", "value_per_kg"],
        )
        return t


def solve_workbook(data: ModelData, msg: bool = False) -> Results:
    return MilkModel(data).solve(msg=msg)
