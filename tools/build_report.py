"""Generate the PBIR report definition for 'LCNRV Inventory.Report'.

Run from the repo root:  python tools/build_report.py
Safe to re-run; it rewrites the report's definition folder.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "LCNRV Inventory.Report"
DEF = REPORT / "definition"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def field(ref):
    """'Table.Column' for columns, 'Table[Measure]' for measures."""
    if "[" in ref:
        ent, prop = ref[:-1].split("[")
        return {"Measure": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}, f"{ent}.{prop}", prop
    ent, prop = ref.split(".", 1)
    return {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}, f"{ent}.{prop}", prop


def projections(refs):
    out = []
    for r in refs:
        f, qref, native = field(r)
        out.append({"field": f, "queryRef": qref, "nativeQueryRef": native})
    return {"projections": out}


def title(text):
    return {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{text}'")}}]}


def visual(name, vtype, pos, roles, objects=None, container=None):
    v = {
        "$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json",
        "name": name,
        "position": {"x": pos[0], "y": pos[1], "z": pos[4] if len(pos) > 4 else 0,
                     "width": pos[2], "height": pos[3], "tabOrder": pos[4] if len(pos) > 4 else 0},
        "visual": {
            "visualType": vtype,
            "query": {"queryState": {role: projections(refs) for role, refs in roles.items()}},
            "drillFilterOtherVisuals": True,
        },
    }
    if objects:
        v["visual"]["objects"] = objects
    if container:
        v["visual"]["visualContainerObjects"] = container
    return v


def slicer(name, pos, ref, label):
    return visual(name, "slicer", pos, {"Values": [ref]},
                  objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]},
                  container=title(label))


def card(name, pos, measure):
    return visual(name, "card", pos, {"Values": [measure]})


MATRIX_VALUES = ["Inventory[Volume]", "Inventory[Unit Cost]", "Inventory[Total Cost]",
                 "Inventory[NRV per Unit]", "Inventory[LCNRV Value]", "Inventory[Write-down]"]

PAGES = [
    ("lcnrvSummary", "LCNRV Summary", [
        slicer("slicerMonth", (16, 12, 240, 64, 0), "Months.Month", "Month"),
        slicer("slicerCategory", (272, 12, 240, 64, 1), "Products.Category", "Category"),
        slicer("slicerLocation", (528, 12, 240, 64, 2), "Inventory.Location", "Location"),
        card("cardVolume", (16, 88, 236, 100, 3), "Inventory[Volume]"),
        card("cardTotalCost", (268, 88, 236, 100, 4), "Inventory[Total Cost]"),
        card("cardLcnrv", (520, 88, 236, 100, 5), "Inventory[LCNRV Value]"),
        card("cardWriteDown", (772, 88, 236, 100, 6), "Inventory[Write-down]"),
        card("cardWriteDownPct", (1024, 88, 240, 100, 7), "Inventory[Write-down %]"),
        visual("chartByMonth", "lineClusteredColumnComboChart", (16, 204, 1248, 200, 8), {
            "Category": ["Months.Month"],
            "Y": ["Inventory[Total Cost]", "Inventory[LCNRV Value]"],
            "Y2": ["Inventory[Write-down]"],
        }, container=title("Cost vs LCNRV value by month")),
        visual("matrixSkuMonth", "pivotTable", (16, 420, 1248, 288, 9), {
            "Rows": ["Products.Category", "Products.SKU"],
            "Columns": ["Months.Month"],
            "Values": MATRIX_VALUES,
        }, container=title("Volume, cost and LCNRV by SKU and month")),
    ]),
    ("lcnrvDetail", "LCNRV Detail", [
        slicer("detailSlicerMonth", (16, 12, 240, 64, 0), "Months.Month", "Month"),
        slicer("detailSlicerCategory", (272, 12, 240, 64, 1), "Products.Category", "Category"),
        slicer("detailSlicerLocation", (528, 12, 240, 64, 2), "Inventory.Location", "Location"),
        visual("detailTable", "tableEx", (16, 88, 1248, 620, 3), {
            "Values": ["Months.Month", "Products.Category", "Products.SKU", "Products.Description",
                       "Inventory.Location", "Inventory[Volume]", "Inventory[Unit Cost]",
                       "Inventory[Total Cost]", "Inventory[Selling Price]", "Inventory[NRV per Unit]",
                       "Inventory[LCNRV Unit Value]", "Inventory[LCNRV Value]", "Inventory[Write-down]",
                       "Inventory[Write-down Movement]"],
        }, container=title("Line-level LCNRV test (SKU x location x month)")),
    ]),
    ("writeDownRollforward", "Write-down Roll-forward", [
        slicer("rfSlicerCategory", (16, 12, 240, 64, 0), "Products.Category", "Category"),
        slicer("rfSlicerLocation", (272, 12, 240, 64, 1), "Inventory.Location", "Location"),
        visual("rfMatrix", "pivotTable", (16, 88, 1248, 360, 2), {
            "Rows": ["Months.Month"],
            "Values": ["Inventory[Volume]", "Inventory[Total Cost]", "Inventory[LCNRV Value]",
                       "Inventory[Write-down Prior Month]", "Inventory[Write-down Movement]",
                       "Inventory[Write-down]", "Inventory[Write-down %]",
                       "Inventory[Lines Written Down]", "Inventory[Lines Missing Price]"],
        }, container=title("Write-down provision roll-forward")),
        visual("rfChart", "clusteredColumnChart", (16, 464, 1248, 244, 3), {
            "Category": ["Months.Month"],
            "Y": ["Inventory[Write-down Movement]"],
        }, container=title("Write-down charge / (release) to COGS by month")),
    ]),
]


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def main():
    if DEF.exists():
        shutil.rmtree(DEF)
    write(DEF / "version.json", {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write(DEF / "report.json", {"$schema": f"{SCHEMA}/report/3.0.0/schema.json", "themeCollection": {}})
    write(DEF / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p[0] for p in PAGES],
        "activePageName": PAGES[0][0],
    })
    for name, display, visuals in PAGES:
        pdir = DEF / "pages" / name
        write(pdir / "page.json", {
            "$schema": f"{SCHEMA}/page/2.0.0/schema.json",
            "name": name, "displayName": display, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
        })
        for v in visuals:
            write(pdir / "visuals" / v["name"] / "visual.json", v)
    print(f"wrote {sum(len(p[2]) for p in PAGES)} visuals on {len(PAGES)} pages")


if __name__ == "__main__":
    main()
