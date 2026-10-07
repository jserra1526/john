"""Build the single-page browser planner.

Inlines web/model.js and the CSVs in data/sample into web/app.html and writes
web/dist/milk-planner.html. The page also needs highs.wasm (from the `highs`
npm package, version pinned in app.html) published next to it.

Run:  python web/build.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB = ROOT / "web"
TABLES = ["components", "supply", "transport", "plant_intake", "lines", "line_rates", "products", "demand"]

page = (WEB / "app.html").read_text()
model = (WEB / "model.js").read_text()
sample = {name: (ROOT / "data" / "sample" / f"{name}.csv").read_text() for name in TABLES}

page = page.replace("/*MODEL_JS*/", model).replace("/*SAMPLE_DATA*/", json.dumps(sample))
out = WEB / "dist" / "milk-planner.html"
out.parent.mkdir(exist_ok=True)
out.write_text(page)
print(f"wrote {out} ({len(page) // 1024} KB)")
