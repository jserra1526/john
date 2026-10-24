# Milk allocation optimiser (prototype)

Optimises how farm milk is allocated to factories and plants, and what products are made,
to maximise profit over a 52-week dairy season. Products are modelled by their milk
components (fat, protein, lactose+ash), so protein standardisation is included.

The network has five collection zones across three states supplying three factories.
All zone, state and factory names are code names.

**Status:** v0 prototype. Milk volumes by state are real (640 ML/season); all other data is **made up**. Read [`docs/design.md`](docs/design.md)
for the scope, formulation, simplifications and roadmap.

## Quick start

```bash
pip install -r requirements.txt

# 1. (Re)generate the sample input workbook
python scripts/make_sample_data.py data/sample_inputs.xlsx

# 2. Run the optimiser
python -m milkopt data/sample_inputs.xlsx -o results.xlsx

# 3. Run the tests
python -m pytest
```

Open `data/sample_inputs.xlsx` to see and edit the inputs (the `README` sheet explains each
tab). `data/sample_results.xlsx` contains the results from the sample data.

## Layout

| Path | Contents |
|---|---|
| `docs/design.md` | Scope, network, formulation, assumptions, roadmap |
| `milkopt/data.py` | Reads and validates the Excel inputs |
| `milkopt/model.py` | The linear programme (PuLP + HiGHS solver) |
| `milkopt/report.py` | Excel results and console summary |
| `scripts/make_sample_data.py` | Generates the made-up sample workbook |
| `tests/` | Checks on mass balance, specs, capacity, stock and input validation |
