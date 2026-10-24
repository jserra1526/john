# Milk Allocation Optimiser — Design (v0)

Status: **prototype on made-up data**. This document records the scope we agreed,
how the model is built, the simplifications in this first version, and what
comes next. It should be reviewed and corrected before the model grows.

All zone, state and site names (Zone 1–5, State A–C, Atlas, Boreas, Cygnus) are code names.

## 1. Purpose

Maximise profit over a 12‑month dairy season (July–June, 52 weekly buckets) by deciding:

1. **Milk allocation**: how much milk from each collection zone is tankered to each factory each week.
2. **Spot milk**: how much milk to sell to, or buy from, other processors.
3. **Product mix**: what each plant makes each week, within its available hours.
4. **Standardisation**: the component make‑up of flexible products (e.g. protein in SMP/WMP)
   within their specifications.
5. **Stock and sales**: how much product to sell or hold each week, within committed and
   maximum sales.

It is a tactical/S&OP planning tool, not a daily schedule.

## 2. Network

```
 Collection zones            Factories              Plants
 ────────────────            ─────────              ──────
 Zone 1 (State A) ──┐
 Zone 2 (State A) ──┼──────► Atlas (State A) ────── Dryer 1 (IF) · Dryer 2 (SMP/WMP/AWP/Perm)
 Zone 3 (State A) ──┤                               Dryer 3 (IF/WMP/SMP) · Cream cheese · Lactoferrin
 Zone 4 (State B) ──┼──────► Boreas (State A) ───── Dryers 1–3 (SMP/WMP/Perm; MPC on D3 only)
 Zone 5 (State C) ──┘                               Butter · Lactoferrin
                    └──────► Cygnus (State B) ───── Cheddar · Stringers · Parmesan
     tanker routes                                  D40 whey dryer · Butter
  (cost $/kL per route)
```

## 3. Components and streams

Milk is tracked as **three solids components plus water**:

| Code | Meaning |
|---|---|
| `fat` | Butterfat |
| `protein` | True/total protein |
| `la` | Lactose + ash (minerals), so fat + protein + la = total solids |

Together these give total solids, which is what lets the model standardise protein.

At each factory, every **stream** is a pool of components (kg):

| Stream | Fed by | Used by |
|---|---|---|
| `MILK` | Tankered and spot milk | All milk products |
| `WHEY` | Cheese making (by‑product) | D40, whey cream into butter |
| `ACID_WHEY` | Cream cheese (by‑product) | Acid whey powder |

**Key assumption (v0):** within a factory, the `MILK` pool can be split freely into any
combination of fat, protein and lactose/ash. That means separation (cream/skim) and
ultrafiltration (retentate/permeate) are available with no cost or capacity limit.
This is how protein standardisation is represented. For example, MPC takes protein out
of the pool, and the lactose left behind goes into SMP/WMP (down to 34% protein in SNF)
or into permeate powder.

Surplus solids that nothing uses are **disposed** at a per‑stream value: whey to stockfeed
at +$0.02/kg, while dumping milk solids costs −$5/kg as a last resort.

## 4. Products

Products are defined in two ways:

| Type | How it works | Examples |
|---|---|---|
| **Fixed recipe** | Fixed kg of fat/protein/la drawn per tonne; fixed kg returned to a by‑product stream (e.g. whey) | Cheddar, stringers, parmesan, cream cheese, butter |
| **Specification** | Each component has a min–max range per tonne; total dairy solids fixed; optional minimum protein/SNF | SMP, WMP, MPC85, permeate, AWP, D40, IF base, lactoferrin |

The infant formula base uses 525 kg of dairy solids per tonne. The rest is purchased
ingredients (oils, lactose, vitamins), charged at a $/t cost.

**Extracted products** such as lactoferrin occur in milk only in tiny amounts (≈0.1 g/L).
So output is also capped by the milk the factory takes in, set in the `max_kg_per_kL_milk`
column of `Products`. The sample uses 0.05 kg/kL (≈50% recovery). Lactoferrin is made at
Atlas and Boreas.

## 5. Mathematical formulation (linear programme)

**Indices:** zone *z*, factory *f*, plant *l*, product *p*, stream *s*, component *c*, week *w*.
A *process* (l, p) is a plant that can make a product.

**Decision variables (all ≥ 0):**

| Variable | Unit | Meaning |
|---|---|---|
| x[z,f,w] | kL | Milk tankered zone → factory |
| sell_spot[z,w] / buy_spot[f,w] | kL | Spot milk sold from a zone / bought into a factory |
| make[l,p,w] | t | Production |
| draw[l,p,s,c,w] | kg | Component drawn from a stream into a process |
| dispose[f,s,c,w] | kg | Surplus component disposed |
| sell[p,w], inv[p,w], short[p,w] | t | Sales, closing stock, unmet commitments |

**Constraints:**

1. **Collect all milk:** Σ_f x[z,f,w] + sell_spot[z,w] = supply[z,w]
2. **Intake capacity:** Σ_z x[z,f,w] + buy_spot[f,w] ≤ intake[f]
3. **Component balance** for each factory, stream, component and week:
   milk in × density × component % + by‑products generated = Σ draws + dispose
4. **Recipes/specs:** for each process and week, with U_c = Σ_s draw[l,p,s,c,w]:
   - fixed: U_c = recipe_c × make
   - spec: min_c × make ≤ U_c ≤ max_c × make, and Σ_c U_c = dairy_solids × make
   - standardisation: U_protein ≥ protein_snf_min × (U_protein + U_la)
5. **Extraction limit:** 1000 × Σ_l make[l,p,w] at factory f ≤ max_kg_per_kL_milk[p] × milk intake[f,w]
6. **Plant hours:** Σ_p make[l,p,w] / rate[l,p] ≤ hours[l,w] (0 hours = shutdown)
7. **Stock:** inv[p,w] = inv[p,w−1] + Σ_l make[l,p,w] − sell[p,w]; inv ≤ max stock;
   closing stock ≥ target
8. **Sales:** sell + short ≥ committed minimum; sell ≤ market maximum

**Objective (maximise season contribution):**

```
  product revenue + spot milk sales − spot milk purchases + disposal value
  − processing & purchased‑ingredient cost − tanker freight − stock holding
  − shortfall penalty
```

The farmgate milk cost ($/kg fat and protein) is fixed because all contracted milk must
be collected. So it doesn't change any decision. It is subtracted afterwards to report
profit.

**Marginal values** (shadow prices) are reported as a key output:

- Value of an extra kL of milk in each zone and week.
- Value of an extra kg of fat, protein or lactose at each factory and week.
- Value of an extra plant hour, showing which plants constrain profit and when.

## 6. Inputs (Excel)

One workbook, one sheet per table, long format (one row per item per week) so it is easy
to filter, pivot and paste into:

`Settings · Weeks · Zones · Supply · Factories · Routes · Streams · Products ·
Product_Inputs · Byproducts · Plants · Processes · Plant_Hours · Market · Spot`

The `README` sheet in `data/sample_inputs.xlsx` describes each one. **All sample data is
made up.**

## 7. Outputs (Excel)

`Summary` (P&L) · `Milk_Allocation` · `Spot_Milk` · `Production` (including achieved
composition) · `Plant_Utilisation` (including value of an extra hour) · `Sales_Stock` ·
`Disposals` · `Marginal_Values` (milk by zone and week) · `Component_Values` (by factory
and week)

## 8. Simplifications in v0 (to revisit)

| # | Simplification | Likely refinement |
|---|---|---|
| 1 | Separation/UF is free and unlimited within a factory | Add separator and UF capacity and cost; cream and skim as explicit streams |
| 2 | No transfers between factories (cream, skim, concentrate, whey) | Add tanker transfers of streams between sites |
| 3 | Stock and sales are national, not by factory or warehouse | Stock per site; freight to port or customer |
| 4 | Plants switch products freely within a week | Campaign/changeover limits (integer variables) |
| 5 | Fixed cheese yields | Yield depending on milk composition (e.g. Van Slyke formula) |
| 6 | Parmesan maturation (~12 months) ignored | Maturation stock with ageing |
| 7 | Dryer capabilities: MPC only on Boreas D3 (confirmed: one MPC dryer, which one assumed); other rates made up | Confirm which dryer makes MPC and the real rates |
| 8 | Tanker fleet capacity not limited | Fleet or driver hours per week |
| 9 | Prices are deterministic | Scenarios (price/supply), sensitivity runs |
| 10 | Farmgate price flat over the season | Monthly step‑ups / incentives (reporting only unless spot milk is affected) |

## 9. What the first run on made‑up data shows

The run solves in about 2 seconds (≈10k variables, ≈12k constraints). Results, all
from invented data:

- **Milk value moves with the season.** The marginal value of an extra kL is about $510–560
  in the spring flush and about $770–800 in winter and autumn. That is the information
  you need to decide spot milk trades and farm incentive payments.
- **Spot milk:** about 140 ML is sold, in the flush when plants are full and in autumn when
  dryers are shut for maintenance. About 100 ML is bought in winter and summer to fill
  spare capacity.
- **Lactoferrin** (≈80 t at a made-up $600k/t) pulls more milk into Atlas and Boreas,
  because each extra kL taken in allows a little more lactoferrin.
- **Bottlenecks:** Boreas butter (≈$11k per extra hour), Atlas cream cheese and the Cygnus
  cheese plants run at 100%. Atlas dryers have spare capacity (62–89%).
- **Cygnus disposes a small amount of milk solids every week** (≈$6m a season). Its fixed
  cheese recipes can't absorb the seasonal change in milk composition, and it has no
  skim/cream outlet. This is the main argument for adding **stream transfers between
  factories** (item 2 in section 8).
- The profit figure excludes fixed costs (labour, overheads, depreciation), so it should
  be read as contribution rather than net profit.

These conclusions only reflect the made‑up numbers. They are here to show the type of
insight the model gives.

## 10. Roadmap (proposed)

1. **v0 (this):** single LP, 52 weeks, 3 factories, made‑up data, Excel in/out.
2. **v1:** replace sample data with real data, validate against a past season.
3. **v2:** stream transfers between factories; separator/UF capacity; stock by site.
4. **v3:** campaign/changeover logic (MIP), composition‑dependent cheese yields, maturation.
5. **v4:** scenario manager and a simple user interface (e.g. web front end or Excel add‑in).

## 11. Open questions

1. Which Boreas dryer is the MPC dryer (D3 assumed), and what are the real rates? Lactoferrin recovery, plant capacity and price?
2. Can cream, skim or whey be transferred between sites today, and at what cost?
3. Which sales are contracted (minimum volumes) versus open commodity sales?
4. Is the farmgate price paid on fat and protein only, or is there a volume charge?
5. How is end‑of‑season stock valued?
6. Are there spot milk contracts with fixed volumes, or is it opportunistic?
