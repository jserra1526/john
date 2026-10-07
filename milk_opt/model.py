"""Multi-period milk allocation and product mix LP.

Each month, milk collected in each region is either sent to a plant, sold on
the spot market, or (as a last resort) dumped. At each plant the milk's
components (fat, protein, ...) are split across products according to each
product's recipe, subject to plant intake and line-hour capacity. Products go
into inventory and are sold against monthly demand. The objective maximises
margin: sales + spot/surplus revenue minus milk, transport, processing,
holding and penalty costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import pulp

from .data import ModelData

DEFAULT_DUMP_PENALTY_PER_T = 10_000.0


@dataclass
class Solution:
    status: str
    objective: float
    flows: pd.DataFrame
    spot: pd.DataFrame
    production: pd.DataFrame
    surplus: pd.DataFrame
    sales: pd.DataFrame
    line_use: pd.DataFrame
    intake: pd.DataFrame
    milk_value: pd.DataFrame
    pnl: dict[str, float] = field(default_factory=dict)


class MilkModel:
    def __init__(self, data: ModelData, must_take_milk: bool = True,
                 dump_penalty_per_t: float = DEFAULT_DUMP_PENALTY_PER_T):
        self.data = data
        self.must_take_milk = must_take_milk
        self.dump_penalty = dump_penalty_per_t
        self.prob = pulp.LpProblem("milk_optimisation", pulp.LpMaximize)
        self._build()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        d = self.data
        months = d.months
        comps = d.component_names
        self.months = months

        supply = d.supply.set_index(["region", "month"])
        products = d.products.set_index("product")
        demand = d.demand.set_index(["product", "month"])
        intake_cap = d.plant_intake.set_index(["plant", "month"])["intake_capacity_t"]
        hours = d.lines.set_index(["plant", "line", "month"])["hours_available"]
        transport = d.transport.set_index(["region", "plant"])["cost_per_t"]
        surplus_value = d.components.set_index("component")["surplus_value_per_kg"]
        self.lane_keys = list(transport.index)
        self.rate_keys = list(d.line_rates.itertuples(index=False))

        prob = self.prob

        def var(name, keys, lowBound=0, upBound=None):
            ub = upBound or (lambda key: None)
            return {key: prob.add_variable("_".join([name, *map(str, key)]).replace("-", "_"), lowBound, ub(key))
                    for key in keys}

        lanes = [(r, p, t) for (r, p) in self.lane_keys for t in months if (r, t) in supply.index]
        self.flow = var("flow", lanes, lowBound=0)
        rt = list(supply.index)
        self.spot = var("spot", rt, upBound=lambda k: supply.at[k, "spot_max_t"])
        self.dump = var("dump", rt, lowBound=0)
        make_keys = [(row.plant, row.line, row.product, t) for row in self.rate_keys for t in months]
        self.make = var("make", make_keys, lowBound=0)
        made_by_product = {}
        for key in make_keys:
            made_by_product.setdefault((key[2], key[3]), []).append(self.make[key])
        plant_months = [(p, t) for p in d.plants for t in months]
        self.surplus = var("surplus", [(p, c, t) for p, t in plant_months for c in comps], lowBound=0)
        pk = [(k, t) for k in d.product_names for t in months]
        self.sales = var("sales", pk, lowBound=0)
        self.short = var("short", pk, lowBound=0)
        self.inv = var("inv", pk, upBound=lambda key: products.at[key[0], "storage_capacity_t"])

        self.supply_con, self.intake_con, self.line_con, self.comp_con = {}, {}, {}, {}

        # Milk supply: every tonne collected goes to a plant, spot, or dump.
        for (r, t) in rt:
            out = pulp.lpSum(self.flow[r, p, t] for p in d.plants if (r, p, t) in self.flow)
            out += self.spot[r, t] + self.dump[r, t]
            vol = supply.at[(r, t), "volume_t"]
            con = (out == vol) if self.must_take_milk else (out <= vol)
            self.supply_con[r, t] = self._add(con, f"supply_{r}_{t}")

        for p, t in plant_months:
            inflow = [(self.flow[r, p, t], supply.loc[(r, t)]) for r in d.regions if (r, p, t) in self.flow]

            # Plant milk intake capacity.
            cap = intake_cap.get((p, t), 0.0)
            con = pulp.lpSum(f for f, _ in inflow) <= cap
            self.intake_con[p, t] = self._add(con, f"intake_{p}_{t}")

            # Component balance: components in = components into products + surplus.
            for c in comps:
                used = pulp.lpSum(
                    self.make[p, row.line, row.product, t] * products.at[row.product, c] / 1000.0
                    for row in self.rate_keys if row.plant == p
                )
                into = pulp.lpSum(f * s[c] / 1000.0 for f, s in inflow)
                con = into == used + self.surplus[p, c, t]
                self.comp_con[p, c, t] = self._add(con, f"component_{p}_{c}_{t}")

        # Line hours.
        for (p, line, t), h in hours.items():
            load = pulp.lpSum(
                self.make[p, line, row.product, t] / row.rate_t_per_hr
                for row in self.rate_keys if row.plant == p and row.line == line
            )
            con = load <= h
            self.line_con[p, line, t] = self._add(con, f"line_{p}_{line}_{t}")

        # Inventory, demand, shelf life.
        for k in d.product_names:
            prev = products.at[k, "initial_inventory_t"]
            life = int(products.at[k, "shelf_life_months"])
            for i, t in enumerate(months):
                made = pulp.lpSum(made_by_product.get((k, t), []))
                prob += self.inv[k, t] == prev + made - self.sales[k, t], f"inv_{k}_{t}"
                prev = self.inv[k, t]

                if (k, t) in demand.index:
                    row = demand.loc[(k, t)]
                    prob += self.sales[k, t] <= row["max_t"], f"dmax_{k}_{t}"
                    prob += self.sales[k, t] + self.short[k, t] >= row["min_t"], f"dmin_{k}_{t}"
                else:
                    prob += self.sales[k, t] == 0, f"dmax_{k}_{t}"

                # Stock held now must be sold within its shelf life. If that window runs
                # past the horizon, stock carried out of the last month also counts.
                if t != months[-1]:
                    outlet = [self.sales[k, f] for f in months[i + 1 : i + 1 + life]]
                    if life > 0 and i + life >= len(months) - 1:
                        outlet.append(self.inv[k, months[-1]])
                    prob += self.inv[k, t] <= pulp.lpSum(outlet), f"life_{k}_{t}"
                elif life == 0:
                    prob += self.inv[k, t] == 0, f"life_{k}_{t}"

            prob += self.inv[k, months[-1]] >= products.at[k, "min_closing_inventory_t"], f"close_{k}"

        # Objective.
        price = lambda k, t: demand.at[(k, t), "price_per_t"] if (k, t) in demand.index else 0.0
        penalty = lambda k, t: (demand.at[(k, t), "shortfall_penalty_per_t"]
                                if (k, t) in demand.index else 0.0)
        self.terms = {
            "product_revenue": pulp.lpSum(self.sales[k, t] * price(k, t) for k, t in pk),
            "spot_milk_revenue": pulp.lpSum(self.spot[k] * supply.at[k, "spot_price_per_t"] for k in rt),
            "surplus_component_value": pulp.lpSum(
                self.surplus[p, c, t] * surplus_value[c] for p, c, t in self.surplus),
            "milk_cost": -pulp.lpSum(
                (pulp.lpSum(self.flow[r, p, t] for p in d.plants if (r, p, t) in self.flow)
                 + self.spot[r, t] + self.dump[r, t]) * supply.at[(r, t), "milk_price_per_t"]
                for r, t in rt),
            "transport_cost": -pulp.lpSum(self.flow[r, p, t] * transport[r, p] for r, p, t in self.flow),
            "processing_cost": -pulp.lpSum(
                self.make[key] * products.at[key[2], "processing_cost_per_t"] for key in make_keys),
            "holding_cost": -pulp.lpSum(
                self.inv[k, t] * products.at[k, "holding_cost_per_t_month"] for k, t in pk),
            "shortfall_penalty": -pulp.lpSum(self.short[k, t] * penalty(k, t) for k, t in pk),
            "dump_penalty": -pulp.lpSum(self.dump[k] * self.dump_penalty for k in rt),
        }
        prob += pulp.lpSum(self.terms.values())

    def _add(self, constraint, name: str) -> str:
        """Add a constraint and return the name it can be looked up by after solving."""
        name = name.replace("-", "_")
        self.prob += constraint, name
        return name

    # ------------------------------------------------------------------ solve
    def solve(self, msg: bool = False, time_limit: float | None = None) -> Solution:
        solver = pulp.HiGHS(msg=msg, timeLimit=time_limit)
        stats = self.prob.solve(solver)
        status = pulp.LpSolveStatus(stats.status).name
        if status != "Optimal":
            raise RuntimeError(f"solver finished with status {status}")
        return self._extract(status)

    def _extract(self, status: str) -> Solution:
        v = lambda x: float(pulp.value(x) or 0.0)
        frame = lambda rows, cols: pd.DataFrame(rows, columns=cols)
        nz = 1e-6

        flows = frame([(r, p, t, v(x)) for (r, p, t), x in self.flow.items() if v(x) > nz],
                      ["region", "plant", "month", "milk_t"])
        spot = frame([(r, t, v(self.spot[r, t]), v(self.dump[r, t])) for r, t in self.spot],
                     ["region", "month", "spot_sold_t", "dumped_t"])
        production = frame([(p, l, k, t, v(x)) for (p, l, k, t), x in self.make.items() if v(x) > nz],
                           ["plant", "line", "product", "month", "made_t"])
        surplus = frame([(p, c, t, v(x)) for (p, c, t), x in self.surplus.items() if v(x) > nz],
                        ["plant", "component", "month", "surplus_kg"])
        sales = frame([(k, t, v(self.sales[k, t]), v(self.short[k, t]), v(self.inv[k, t]))
                       for k, t in self.sales], ["product", "month", "sold_t", "shortfall_t", "closing_inv_t"])
        con = self.prob.get_constraint_by_name
        # HiGHS reports duals for the minimisation form; flip so a shadow price is
        # the change in margin per unit increase of the right-hand side.
        dual = lambda c: -(c.pi or 0.0)
        # For "load <= cap" constraints, constant = -cap and value() = load - cap.
        rows = []
        for (p, l, t), name in self.line_con.items():
            c = con(name)
            hours = -c.constant
            used = hours + v(c)
            rows.append((p, l, t, used, hours, used / hours if hours else 0.0, dual(c)))
        line_use = frame(rows, ["plant", "line", "month", "hours_used", "hours_available",
                                "utilisation", "shadow_price_per_hr"])
        rows = []
        for (p, t), name in self.intake_con.items():
            c = con(name)
            cap = -c.constant
            used = cap + v(c)
            rows.append((p, t, used, cap, used / cap if cap else 0.0, dual(c)))
        intake = frame(rows, ["plant", "month", "milk_in_t", "intake_capacity_t",
                              "utilisation", "shadow_price_per_t"])
        milk_value = frame([(r, t, dual(con(name))) for (r, t), name in self.supply_con.items()],
                           ["region", "month", "marginal_value_per_t"])
        pnl = {name: v(expr) for name, expr in self.terms.items()}
        pnl["margin"] = v(self.prob.objective)
        return Solution(status, pnl["margin"], flows, spot, production, surplus, sales,
                        line_use, intake, milk_value, pnl)


def optimise(data: ModelData, **kwargs) -> Solution:
    solve_kwargs = {k: kwargs.pop(k) for k in ("msg", "time_limit") if k in kwargs}
    return MilkModel(data, **kwargs).solve(**solve_kwargs)
