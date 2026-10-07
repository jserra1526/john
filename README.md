# Milk optimisation model

A multi-period linear program that decides, month by month:

- **where milk goes** – from each supply region to a plant, the spot market, or (last resort) dumped;
- **what each plant makes** – splitting the milk's fat and protein across products on each line;
- **what to stock and sell** – carrying product inventory between months to serve demand,

so as to **maximise margin** within plant intake, line-hour, storage and shelf-life limits.

## Quick start

```bash
pip install -r requirements.txt
python -m milk_opt data/sample --out output   # solve and print a summary
python -m pytest                               # run tests
python scripts/make_sample_data.py             # regenerate the sample data
```

Results are written as CSVs to `output/` (`flows`, `spot`, `production`, `surplus`, `sales`,
`line_use`, `intake`, `milk_value`, `pnl`).

Options: `--allow-uncollected` (supply is an upper bound, not must-take), `--dump-penalty`,
`--time-limit`, `--verbose`.

## Model

**Sets:** regions *r*, plants *p*, lines *l*, products *k*, components *c* (e.g. fat, protein), months *t*.

**Decisions:** milk flow `flow[r,p,t]`, spot sale `spot[r,t]`, dumped milk `dump[r,t]`,
production `make[p,l,k,t]`, unused components `surplus[p,c,t]`, `sales[k,t]`,
contract `short[k,t]`, inventory `inv[k,t]`.

| Constraint | Meaning |
|---|---|
| Milk supply | Σ_p flow + spot + dump = volume (≤ with `--allow-uncollected`). Milk can't be stored. |
| Spot limit | spot ≤ `spot_max_t` |
| Plant intake | Σ_r flow ≤ `intake_capacity_t` |
| Component balance | Σ_r flow × milk composition = Σ make × recipe + surplus, for each component |
| Line hours | Σ_k make / rate ≤ `hours_available` (products on a line share its hours) |
| Inventory | inv[t] = inv[t-1] + Σ make − sales; inv ≤ `storage_capacity_t` |
| Demand | sales ≤ `max_t`; sales + short ≥ `min_t` |
| Shelf life | stock on hand ≤ sales over the next `shelf_life_months` (0 = no stock) |
| Closing stock | inv[last month] ≥ `min_closing_inventory_t` |

**Objective (maximise):** product revenue + spot milk revenue + surplus component value
− milk cost − transport − processing − holding − shortfall penalty − dump penalty.

Working on components rather than litres means the model chooses the product mix the way a
dairy planner does: butter consumes fat, SMP consumes protein, cheese and WMP consume both,
and seasonal changes in milk composition shift the best mix.

### Reading the outputs

- `line_use.shadow_price_per_hr` – margin gained from one more hour on that line in that month.
  Non-zero values show where capacity is the bottleneck.
- `intake.shadow_price_per_t` – value of one more tonne of plant intake capacity.
- `milk_value.marginal_value_per_t` – change in margin from one more tonne of milk in that
  region/month (already net of the milk price). Negative at peak means extra milk loses money
  because the plants are full.

## Input data

All files are CSV in one directory (see `data/sample/`). Months are `YYYY-MM`.
Component columns (`fat`, `protein`, …) must match `components.csv` and are kg per tonne.

| File | Columns |
|---|---|
| `components.csv` | component, surplus_value_per_kg |
| `supply.csv` | region, month, volume_t, milk_price_per_t, spot_price_per_t, spot_max_t, *components (kg/t milk)* |
| `transport.csv` | region, plant, cost_per_t — only listed lanes are allowed |
| `plant_intake.csv` | plant, month, intake_capacity_t |
| `lines.csv` | plant, line, month, hours_available |
| `line_rates.csv` | plant, line, product, rate_t_per_hr |
| `products.csv` | product, processing_cost_per_t, holding_cost_per_t_month, storage_capacity_t, initial_inventory_t, min_closing_inventory_t, shelf_life_months, *components (kg/t product, incl. losses)* |
| `demand.csv` | product, month, min_t, max_t, price_per_t, shortfall_penalty_per_t |

The sample data is illustrative only: three regions with a spring-peak milk curve, three plants
(two with dryers, two with cheese lines, maintenance shutdowns in winter) and five products.

## Simplifications / possible extensions

- Inventory is pooled nationally (no plant-to-port logistics or inter-plant transfers of cream/skim).
- Linear economics: no minimum run lengths, changeovers or start-up costs (would need integers).
- Shelf life is an approximation (stock must be coverable by upcoming sales), not batch tracking.
- Prices and demand are deterministic; scenarios could be added for price/milk uncertainty.
