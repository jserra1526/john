// Browser/Node port of milk_opt/model.py. Builds the same LP as the Python
// model, solves it with highs-js and returns the same result tables.
(function (root) {
  "use strict";

  const REQUIRED = {
    components: ["component", "surplus_value_per_kg"],
    supply: ["region", "month", "volume_t", "milk_price_per_t", "spot_price_per_t", "spot_max_t"],
    transport: ["region", "plant", "cost_per_t"],
    plant_intake: ["plant", "month", "intake_capacity_t"],
    lines: ["plant", "line", "month", "hours_available"],
    line_rates: ["plant", "line", "product", "rate_t_per_hr"],
    products: ["product", "processing_cost_per_t", "holding_cost_per_t_month", "storage_capacity_t",
      "initial_inventory_t", "min_closing_inventory_t", "shelf_life_months"],
    demand: ["product", "month", "min_t", "max_t", "price_per_t", "shortfall_penalty_per_t"],
  };
  const TEXT_COLUMNS = new Set(["component", "region", "month", "plant", "line", "product"]);

  // ---------------------------------------------------------------- CSV
  function parseCSV(text) {
    const rows = [];
    let row = [], cell = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (ch === '"') quoted = false;
        else cell += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ",") { row.push(cell); cell = ""; }
      else if (ch === "\n" || ch === "\r") {
        if (ch === "\r" && text[i + 1] === "\n") i++;
        row.push(cell); cell = "";
        if (row.some((c) => c.trim() !== "")) rows.push(row);
        row = [];
      } else cell += ch;
    }
    row.push(cell);
    if (row.some((c) => c.trim() !== "")) rows.push(row);
    if (!rows.length) return [];
    const header = rows[0].map((h) => h.trim());
    return rows.slice(1).map((r) => {
      const o = {};
      header.forEach((h, j) => {
        const v = (r[j] ?? "").trim();
        o[h] = TEXT_COLUMNS.has(h) || v === "" || isNaN(Number(v)) ? v : Number(v);
      });
      return o;
    });
  }

  function toCSV(rows, columns) {
    columns = columns || (rows.length ? Object.keys(rows[0]) : []);
    const esc = (v) => {
      const s = typeof v === "number" ? String(Math.round(v * 1e4) / 1e4) : String(v ?? "");
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    return [columns.join(","), ...rows.map((r) => columns.map((c) => esc(r[c])).join(","))].join("\n");
  }

  // ---------------------------------------------------------------- validation
  function validate(data) {
    const errors = [];
    for (const [name, cols] of Object.entries(REQUIRED)) {
      const t = data[name];
      if (!t || !t.length) { errors.push(`${name}.csv is missing or empty`); continue; }
      const missing = cols.filter((c) => !(c in t[0]));
      if (missing.length) errors.push(`${name}.csv is missing columns: ${missing.join(", ")}`);
    }
    if (errors.length) return errors;
    const comps = data.components.map((c) => c.component);
    for (const name of ["supply", "products"]) {
      const missing = comps.filter((c) => !(c in data[name][0]));
      if (missing.length) errors.push(`${name}.csv needs a column per component; missing ${missing.join(", ")}`);
    }
    const months = new Set(data.supply.map((r) => r.month));
    const plants = new Set(data.plant_intake.map((r) => r.plant));
    const regions = new Set(data.supply.map((r) => r.region));
    const products = new Set(data.products.map((r) => r.product));
    const check = (label, values, allowed) => {
      const bad = [...new Set(values)].filter((v) => !allowed.has(v));
      if (bad.length) errors.push(`${label} references unknown values: ${bad.join(", ")}`);
    };
    check("transport.region", data.transport.map((r) => r.region), regions);
    check("transport.plant", data.transport.map((r) => r.plant), plants);
    check("lines.plant", data.lines.map((r) => r.plant), plants);
    check("lines.month", data.lines.map((r) => r.month), months);
    check("plant_intake.month", data.plant_intake.map((r) => r.month), months);
    check("line_rates.product", data.line_rates.map((r) => r.product), products);
    check("demand.product", data.demand.map((r) => r.product), products);
    check("demand.month", data.demand.map((r) => r.month), months);
    const lineKeys = new Set(data.lines.map((r) => `${r.plant}|${r.line}`));
    check("line_rates (plant, line)", data.line_rates.map((r) => `${r.plant}|${r.line}`), lineKeys);
    if (data.line_rates.some((r) => !(r.rate_t_per_hr > 0))) errors.push("line_rates.rate_t_per_hr must be positive");
    if (data.demand.some((r) => r.min_t > r.max_t)) errors.push("demand.min_t must not exceed demand.max_t");
    for (const name of Object.keys(REQUIRED)) {
      for (const row of data[name]) {
        for (const [k, v] of Object.entries(row)) {
          if (!TEXT_COLUMNS.has(k) && typeof v !== "number") {
            errors.push(`${name}.csv: "${k}" must be a number (found "${v}")`);
            break;
          }
        }
        if (errors.length > 20) return errors;
      }
    }
    return errors;
  }

  // ---------------------------------------------------------------- model
  function build(data, opts = {}) {
    const mustTake = opts.mustTakeMilk !== false;
    const dumpPenalty = opts.dumpPenaltyPerT ?? 10000;
    const comps = data.components.map((c) => c.component);
    const months = [...new Set(data.supply.map((r) => r.month))].sort();
    const regions = [...new Set(data.supply.map((r) => r.region))].sort();
    const plants = [...new Set(data.plant_intake.map((r) => r.plant))].sort();
    const productNames = data.products.map((r) => r.product);
    const K = (...a) => a.join("|");
    const index = (rows, keys) => new Map(rows.map((r) => [K(...keys.map((k) => r[k])), r]));
    const supply = index(data.supply, ["region", "month"]);
    const products = index(data.products, ["product"]);
    const demand = index(data.demand, ["product", "month"]);
    const intake = index(data.plant_intake, ["plant", "month"]);
    const transport = index(data.transport, ["region", "plant"]);
    const surplusValue = new Map(data.components.map((c) => [c.component, c.surplus_value_per_kg]));

    const vars = []; // {name, key, ub}
    const addVar = (group, key, ub = Infinity) => {
      vars.push({ group, key, ub, name: `x${vars.length}` });
      return vars.length - 1;
    };
    const cons = []; // {terms: [[i, coef]], sense, rhs, group, key}
    const addCon = (group, key, terms, sense, rhs) => {
      cons.push({ group, key, terms, sense, rhs, name: `c${cons.length}` });
    };

    const flow = new Map(), spot = new Map(), dump = new Map(), make = new Map();
    const surplus = new Map(), sales = new Map(), short = new Map(), inv = new Map();
    for (const r of data.transport)
      for (const t of months)
        if (supply.has(K(r.region, t))) flow.set(K(r.region, r.plant, t), addVar("flow", [r.region, r.plant, t]));
    for (const s of data.supply) {
      spot.set(K(s.region, s.month), addVar("spot", [s.region, s.month], s.spot_max_t));
      dump.set(K(s.region, s.month), addVar("dump", [s.region, s.month]));
    }
    const madeBy = new Map();
    for (const lr of data.line_rates)
      for (const t of months) {
        const i = addVar("make", [lr.plant, lr.line, lr.product, t]);
        make.set(K(lr.plant, lr.line, lr.product, t), i);
        const mk = K(lr.product, t);
        if (!madeBy.has(mk)) madeBy.set(mk, []);
        madeBy.get(mk).push(i);
      }
    for (const p of plants) for (const t of months) for (const c of comps)
      surplus.set(K(p, c, t), addVar("surplus", [p, c, t]));
    for (const k of productNames) for (const t of months) {
      sales.set(K(k, t), addVar("sales", [k, t]));
      short.set(K(k, t), addVar("short", [k, t]));
      inv.set(K(k, t), addVar("inv", [k, t], products.get(k).storage_capacity_t));
    }

    // Milk supply.
    for (const s of data.supply) {
      const terms = plants.filter((p) => flow.has(K(s.region, p, s.month)))
        .map((p) => [flow.get(K(s.region, p, s.month)), 1]);
      terms.push([spot.get(K(s.region, s.month)), 1], [dump.get(K(s.region, s.month)), 1]);
      addCon("supply", [s.region, s.month], terms, mustTake ? "=" : "<=", s.volume_t);
    }
    // Plant intake and component balance.
    for (const p of plants) for (const t of months) {
      const inflow = regions.filter((r) => flow.has(K(r, p, t))).map((r) => [flow.get(K(r, p, t)), supply.get(K(r, t))]);
      addCon("intake", [p, t], inflow.map(([i]) => [i, 1]), "<=", intake.get(K(p, t))?.intake_capacity_t ?? 0);
      for (const c of comps) {
        const terms = inflow.map(([i, s]) => [i, s[c] / 1000]);
        for (const lr of data.line_rates) if (lr.plant === p)
          terms.push([make.get(K(p, lr.line, lr.product, t)), -products.get(lr.product)[c] / 1000]);
        terms.push([surplus.get(K(p, c, t)), -1]);
        addCon("component", [p, c, t], terms, "=", 0);
      }
    }
    // Line hours.
    for (const l of data.lines) {
      const terms = data.line_rates.filter((lr) => lr.plant === l.plant && lr.line === l.line)
        .map((lr) => [make.get(K(l.plant, l.line, lr.product, l.month)), 1 / lr.rate_t_per_hr]);
      if (terms.length) addCon("line", [l.plant, l.line, l.month], terms, "<=", l.hours_available);
    }
    // Inventory, demand, shelf life, closing stock.
    for (const k of productNames) {
      const prod = products.get(k);
      const life = Math.round(prod.shelf_life_months);
      const last = months[months.length - 1];
      months.forEach((t, i) => {
        const terms = [[inv.get(K(k, t)), 1], [sales.get(K(k, t)), 1]];
        for (const m of madeBy.get(K(k, t)) || []) terms.push([m, -1]);
        let rhs = prod.initial_inventory_t;
        if (i > 0) terms.push([inv.get(K(k, months[i - 1])), -1]), (rhs = 0);
        addCon("inv", [k, t], terms, "=", rhs);

        const d = demand.get(K(k, t));
        if (d) {
          addCon("dmax", [k, t], [[sales.get(K(k, t)), 1]], "<=", d.max_t);
          addCon("dmin", [k, t], [[sales.get(K(k, t)), 1], [short.get(K(k, t)), 1]], ">=", d.min_t);
        } else addCon("dmax", [k, t], [[sales.get(K(k, t)), 1]], "<=", 0);

        if (t !== last) {
          const lt = [[inv.get(K(k, t)), 1]];
          for (const f of months.slice(i + 1, i + 1 + life)) lt.push([sales.get(K(k, f)), -1]);
          if (life > 0 && i + life >= months.length - 1) lt.push([inv.get(K(k, last)), -1]);
          addCon("life", [k, t], lt, "<=", 0);
        } else if (life === 0) addCon("life", [k, t], [[inv.get(K(k, t)), 1]], "=", 0);
      });
      addCon("close", [k], [[inv.get(K(k, last)), 1]], ">=", prod.min_closing_inventory_t);
    }

    // Objective, kept in named groups for the P&L.
    const pnl = {
      product_revenue: [], spot_milk_revenue: [], surplus_component_value: [], milk_cost: [],
      transport_cost: [], processing_cost: [], holding_cost: [], shortfall_penalty: [], dump_penalty: [],
    };
    for (const [key, i] of sales) {
      const d = demand.get(key);
      if (d) pnl.product_revenue.push([i, d.price_per_t]);
    }
    for (const [key, i] of short) {
      const d = demand.get(key);
      if (d) pnl.shortfall_penalty.push([i, -d.shortfall_penalty_per_t]);
    }
    for (const [key, i] of spot) pnl.spot_milk_revenue.push([i, supply.get(key).spot_price_per_t]);
    for (const [key, i] of surplus) pnl.surplus_component_value.push([i, surplusValue.get(vars[i].key[1])]);
    for (const [key, i] of flow) {
      const [r, p, t] = vars[i].key;
      pnl.milk_cost.push([i, -supply.get(K(r, t)).milk_price_per_t]);
      pnl.transport_cost.push([i, -transport.get(K(r, p)).cost_per_t]);
    }
    for (const [key, i] of spot) pnl.milk_cost.push([i, -supply.get(key).milk_price_per_t]);
    for (const [key, i] of dump) {
      pnl.milk_cost.push([i, -supply.get(key).milk_price_per_t]);
      pnl.dump_penalty.push([i, -dumpPenalty]);
    }
    for (const [, i] of make) pnl.processing_cost.push([i, -products.get(vars[i].key[2]).processing_cost_per_t]);
    for (const [, i] of inv) pnl.holding_cost.push([i, -products.get(vars[i].key[0]).holding_cost_per_t_month]);

    const objective = new Map();
    for (const terms of Object.values(pnl))
      for (const [i, c] of terms) objective.set(i, (objective.get(i) || 0) + c);

    return { vars, cons, objective, pnl, months, regions, plants, productNames, comps };
  }

  function num(x) {
    if (!isFinite(x)) throw new Error(`model has a non-numeric coefficient (${x}); check the data`);
    return Math.abs(x) < 1e-12 ? "0" : String(+x.toPrecision(12));
  }

  function linear(terms) {
    const parts = [];
    terms.forEach(([i, c], j) => {
      if (c === 0) return;
      const sign = c < 0 ? "-" : "+";
      parts.push(`${j === 0 && sign === "+" ? "" : sign + " "}${num(Math.abs(c))} x${i}`);
    });
    if (!parts.length) parts.push("0 x0");
    const lines = [];
    for (let j = 0; j < parts.length; j += 8) lines.push(parts.slice(j, j + 8).join(" "));
    return lines.join("\n  ");
  }

  function toLP(m) {
    const out = ["Maximize", " obj: " + linear([...m.objective])];
    out.push("Subject To");
    for (const c of m.cons) out.push(` ${c.name}: ${linear(c.terms)} ${c.sense} ${num(c.rhs)}`);
    out.push("Bounds");
    for (const v of m.vars) out.push(isFinite(v.ub) ? ` 0 <= ${v.name} <= ${num(v.ub)}` : ` ${v.name} >= 0`);
    out.push("End");
    return out.join("\n");
  }

  // ---------------------------------------------------------------- solve
  function solve(highs, data, opts = {}) {
    const m = build(data, opts);
    const res = highs.solve(toLP(m), { output_flag: false });
    if (res.Status !== "Optimal") {
      const hint = res.Status === "Infeasible"
        ? "No plan meets every hard limit. Check closing-stock targets, shelf life and line hours."
        : "";
      throw new Error(`Solver finished with status: ${res.Status}. ${hint}`.trim());
    }
    const x = (i) => res.Columns[`x${i}`]?.Primal ?? 0;
    const rows = new Map(res.Rows.map((r) => [r.Name, r]));
    // Shadow price: change in margin per unit increase of the constraint's limit.
    const dual = (c) => rows.get(c.name)?.Dual ?? 0;
    const activity = (c) => c.terms.reduce((s, [i, k]) => s + k * x(i), 0);
    const pick = (group) => m.vars.map((v, i) => [v, i]).filter(([v]) => v.group === group);
    const nz = 1e-6;
    const byKey = (group) => new Map(pick(group).map(([v, i]) => [v.key.join("|"), x(i)]));
    const salesV = byKey("sales"), shortV = byKey("short"), invV = byKey("inv"), dumpV = byKey("dump");

    const result = {
      status: res.Status,
      months: m.months, regions: m.regions, plants: m.plants, products: m.productNames,
      flows: pick("flow").filter(([, i]) => x(i) > nz)
        .map(([v, i]) => ({ region: v.key[0], plant: v.key[1], month: v.key[2], milk_t: x(i) })),
      spot: pick("spot").map(([v, i]) => ({
        region: v.key[0], month: v.key[1], spot_sold_t: x(i), dumped_t: dumpV.get(v.key.join("|")) })),
      production: pick("make").filter(([, i]) => x(i) > nz)
        .map(([v, i]) => ({ plant: v.key[0], line: v.key[1], product: v.key[2], month: v.key[3], made_t: x(i) })),
      surplus: pick("surplus").filter(([, i]) => x(i) > nz)
        .map(([v, i]) => ({ plant: v.key[0], component: v.key[1], month: v.key[2], surplus_kg: x(i) * 1000 })),
      sales: pick("sales").map(([v]) => {
        const k = v.key.join("|");
        return { product: v.key[0], month: v.key[1], sold_t: salesV.get(k), shortfall_t: shortV.get(k), closing_inv_t: invV.get(k) };
      }),
      line_use: m.cons.filter((c) => c.group === "line").map((c) => {
        const used = activity(c);
        return { plant: c.key[0], line: c.key[1], month: c.key[2], hours_used: used, hours_available: c.rhs,
          utilisation: c.rhs ? used / c.rhs : 0, shadow_price_per_hr: dual(c) };
      }),
      intake: m.cons.filter((c) => c.group === "intake").map((c) => {
        const used = activity(c);
        return { plant: c.key[0], month: c.key[1], milk_in_t: used, intake_capacity_t: c.rhs,
          utilisation: c.rhs ? used / c.rhs : 0, shadow_price_per_t: dual(c) };
      }),
      milk_value: m.cons.filter((c) => c.group === "supply")
        .map((c) => ({ region: c.key[0], month: c.key[1], marginal_value_per_t: dual(c) })),
      pnl: {},
    };
    for (const [name, terms] of Object.entries(m.pnl))
      result.pnl[name] = terms.reduce((s, [i, c]) => s + c * x(i), 0);
    result.pnl.margin = Object.values(result.pnl).reduce((a, b) => a + b, 0);
    result.objective = result.pnl.margin;
    return result;
  }

  const api = { REQUIRED, parseCSV, toCSV, validate, build, toLP, solve };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.MilkModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
