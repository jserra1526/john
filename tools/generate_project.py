"""Generates the SalesReport Power BI Project (PBIP) into the target directory.

Usage: python tools/generate_project.py <output-dir>
"""
import csv, json, os, random, shutil, sys, uuid
from collections import defaultdict
from datetime import date, timedelta

OUT = sys.argv[1]
NAME = "SalesReport"
random.seed(42)
uid = lambda: str(uuid.UUID(int=random.getrandbits(128), version=4))

def write(path, text):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)

def wjson(path, obj):
    write(path, json.dumps(obj, indent=2) + "\n")

def wcsv(fname, rows):
    full = os.path.join(OUT, "data", fname)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

# Start from a clean slate so renamed pages/visuals don't leave stale folders behind.
for d in (f"{NAME}.Report", f"{NAME}.SemanticModel", "data"):
    shutil.rmtree(os.path.join(OUT, d), ignore_errors=True)

# ---------------------------------------------------------------- sample data
# Actuals run from Jan 2025 to the end of Sep 2026; plan versions cover FY2026.
ACT_START, ACT_END, PLAN_YEAR = date(2025, 1, 1), date(2026, 9, 30), 2026
VERSIONS = [("Budget", 1, 0), ("Q1 Forecast", 2, 3), ("Q2 Forecast", 3, 6), ("Latest Estimate", 4, 9)]
# (version, sort order, months of actuals included before the forecast starts)

catalog = {
    "Bikes": [("Road Bike", 1450, 900), ("Mountain Bike", 1200, 720), ("Hybrid Bike", 850, 510),
              ("Kids Bike", 320, 180), ("E-Bike", 2600, 1750)],
    "Accessories": [("Helmet", 75, 32), ("Bike Lock", 45, 18), ("Water Bottle", 12, 4),
                    ("Bike Light Set", 55, 22), ("Pump", 35, 14)],
    "Clothing": [("Jersey", 65, 26), ("Cycling Shorts", 70, 30), ("Gloves", 28, 10),
                 ("Rain Jacket", 120, 55), ("Socks", 14, 5)],
    "Components": [("Tire", 48, 22), ("Chain", 38, 16), ("Brake Pads", 25, 9),
                   ("Saddle", 85, 38), ("Pedals", 60, 25)],
}
# 2026 list price changes by category (budget assumed +3% across the board)
PRICE_CHANGE_2026 = {"Bikes": 0.06, "Accessories": 0.02, "Clothing": 0.04, "Components": -0.02}
BUDGET_PRICE, BUDGET_VOLUME = 0.03, 0.12

products, price_2025, pid = [], {}, 100
for cat, items in catalog.items():
    for name, price, cost in items:
        pid += 1
        price_2025[pid] = price
        products.append({"Product ID": pid, "Product": name, "Category": cat,
                         "Unit Price": round(price * (1 + PRICE_CHANGE_2026[cat]), 2), "Unit Cost": cost})
category_of = {p["Product ID"]: p["Category"] for p in products}

regions = {"North America": ["United States", "Canada", "Mexico"],
           "Europe": ["United Kingdom", "Germany", "France", "Spain"],
           "Asia Pacific": ["Australia", "Japan", "Singapore"]}
segments = ["Consumer", "Small Business", "Enterprise"]
first = ["Summit", "Velo", "Ridge", "Coastal", "Metro", "Alpine", "Urban", "Pioneer", "Trail", "Harbor",
         "Granite", "Swift", "Cedar", "Atlas", "Bright"]
second = ["Cycles", "Sports", "Outfitters", "Bike Co", "Riders", "Gear", "Wheels", "Supply"]
customers, used = [], set()
for i in range(1, 81):
    while True:
        n = f"{random.choice(first)} {random.choice(second)}"
        if n not in used:
            used.add(n)
            break
    region = random.choices(list(regions), weights=[5, 4, 3])[0]
    customers.append({"Customer ID": 1000 + i, "Customer": n,
                      "Segment": random.choices(segments, weights=[5, 3, 2])[0],
                      "Region": region, "Country": random.choice(regions[region])})

sales, order_id, d = [], 50000, ACT_START
while d <= ACT_END:
    seasonal = 1.0 + 0.45 * (d.month in (4, 5, 6, 7, 8)) + 0.3 * (d.month in (11, 12))
    growth = 1.06 if d.year == 2026 else 1.0
    weights = [(3.4 if d.year == 2026 else 3) if p["Category"] == "Bikes"
               else (5 if d.year == 2026 and p["Category"] == "Components" else 6) for p in products]
    for _ in range(max(0, int(random.gauss(4.0 * seasonal * growth, 1.5)))):
        order_id += 1
        cust = random.choice(customers)
        for _ in range(random.choice([1, 1, 1, 2, 2, 3])):
            p = random.choices(products, weights=weights)[0]
            qty = random.randint(1, 2) if p["Category"] == "Bikes" else random.randint(1, 6)
            if cust["Segment"] == "Enterprise":
                qty *= 3
            price = p["Unit Price"] if d.year == 2026 else price_2025[p["Product ID"]]
            sales.append({"Order ID": order_id, "Order Date": d.isoformat(), "Customer ID": cust["Customer ID"],
                          "Product ID": p["Product ID"], "Quantity": qty, "Unit Price": price,
                          "Discount": random.choice([0, 0, 0, 0, 0.05, 0.1, 0.15]),
                          "_region": cust["Region"]})
    d += timedelta(days=1)

# Actuals aggregated to the plan grain: (year, month, product, region) -> [units, net sales]
actual = defaultdict(lambda: [0, 0.0])
for s in sales:
    od = date.fromisoformat(s["Order Date"])
    a = actual[(od.year, od.month, s["Product ID"], s["_region"])]
    a[0] += s["Quantity"]
    a[1] += s["Quantity"] * s["Unit Price"] * (1 - s["Discount"])
for s in sales:
    del s["_region"]

keys = [(m, p["Product ID"], r) for m in range(1, 13) for p in products for r in regions]
# Budget: prior-year volume plus growth, prior-year net price plus the planned price increase.
budget = {}
for m, p, r in keys:
    u, v = actual.get((PLAN_YEAR - 1, m, p, r), (0, 0.0))
    budget[(m, p, r)] = (round(u * (1 + BUDGET_VOLUME)), v / u * (1 + BUDGET_PRICE) if u else 0.0)

plan = []
for version, _, closed in VERSIONS:
    # Forecast months: budget volume scaled by each category's year-to-date run-rate vs budget,
    # priced at each product's year-to-date actual net price.
    ytd_act, ytd_bud, ytd_px = defaultdict(int), defaultdict(int), defaultdict(lambda: [0, 0.0])
    for m, p, r in keys:
        if m <= closed:
            u, v = actual.get((PLAN_YEAR, m, p, r), (0, 0.0))
            ytd_act[category_of[p]] += u
            ytd_bud[category_of[p]] += budget[(m, p, r)][0]
            ytd_px[p][0] += u
            ytd_px[p][1] += v
    for m, p, r in keys:
        if m <= closed:
            units, value = actual.get((PLAN_YEAR, m, p, r), (0, 0.0))
        else:
            bu, bp = budget[(m, p, r)]
            ratio = ytd_act[category_of[p]] / ytd_bud[category_of[p]] if ytd_bud[category_of[p]] else 1.0
            units = round(bu * ratio)
            price = ytd_px[p][1] / ytd_px[p][0] if ytd_px[p][0] else bp
            value = units * price
        if units:
            plan.append({"Scenario": version, "Month": date(PLAN_YEAR, m, 1).isoformat(), "Product ID": p,
                         "Region": r, "Units": units, "Sales": round(value, 2)})

wcsv("Products.csv", products)
wcsv("Customers.csv", customers)
wcsv("Sales.csv", sales)
wcsv("Plan.csv", plan)
wcsv("Regions.csv", [{"Region": r} for r in regions])

# --------------------------------------------------------------- PBIP root
wjson(f"{NAME}.pbip", {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    "version": "1.0",
    "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
    "settings": {"enableAutoRecovery": True},
})
write(".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")

def platform(kind):
    return {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": kind, "displayName": NAME},
            "config": {"version": "2.0", "logicalId": uid()}}

# ---------------------------------------------------------- semantic model
SM = f"{NAME}.SemanticModel"
wjson(f"{SM}/.platform", platform("SemanticModel"))
wjson(f"{SM}/definition.pbism", {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "version": "4.2",
    "settings": {},
})
write(f"{SM}/definition/database.tmdl", "database\n\tcompatibilityLevel: 1600\n\n")

TABLES = ["Sales", "Plan", "Products", "Customers", "Regions", "Calendar", "Scenario", "Variance Bridge"]

def q(name):
    return f"'{name}'" if any(c in name for c in " .-%") or name in ("Date",) else name

write(f"{SM}/definition/model.tmdl",
      "model Model\n"
      "\tculture: en-US\n"
      "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
      "\tsourceQueryCulture: en-US\n"
      "\tdataAccessOptions\n"
      "\t\tlegacyRedirects\n"
      "\t\treturnErrorValuesAsNull\n\n"
      f"annotation PBI_QueryOrder = {json.dumps(['DataFolder'] + TABLES)}\n\n"
      "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
      + "".join(f"ref table {q(t)}\n" for t in TABLES) + "\n")

write(f"{SM}/definition/expressions.tmdl",
      'expression DataFolder = "C:\\PowerBI\\SalesReport\\data\\" '
      'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
      f"\tlineageTag: {uid()}\n\n"
      "\tannotation PBI_NavigationStepName = Navigation\n\n"
      "\tannotation PBI_ResultType = Text\n\n")

TYPES = {"int64": "Int64.Type", "double": "type number", "string": "type text", "dateTime": "type date"}

def column(name, dtype, fmt=None, summarize="none", extra=(), expr=None):
    head = f"\tcolumn {q(name)} = {expr}" if expr else f"\tcolumn {q(name)}"
    lines = [head, f"\t\tdataType: {dtype}"]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    lines += [f"\t\tlineageTag: {uid()}", f"\t\tsummarizeBy: {summarize}"]
    if not expr:
        lines.append(f"\t\tsourceColumn: {name}")
    lines += [f"\t\t{e}" for e in extra]
    lines += ["", "\t\tannotation SummarizationSetBy = Automatic", "", ""]
    return "\n".join(lines)

def measure(name, expr, fmt=None, folder=None):
    expr = expr.strip("\n")
    if "\n" in expr:
        head = f"\tmeasure {q(name)} =\n" + "\n".join("\t\t\t" + line for line in expr.split("\n"))
    else:
        head = f"\tmeasure {q(name)} = {expr}"
    lines = [head]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    if folder:
        lines.append(f"\t\tdisplayFolder: {folder}")
    lines += [f"\t\tlineageTag: {uid()}", "", ""]
    return "\n".join(lines)

def m_partition(table, body):
    expr = "\n".join("\t\t\t\t" + line for line in body.strip("\n").split("\n"))
    return f"\tpartition {q(table)} = m\n\t\tmode: import\n\t\tsource =\n{expr}\n\n"

def csv_partition(table, fname, cols):
    types = ", ".join(f'{{"{c}", {TYPES[t]}}}' for c, t, *_ in cols)
    return m_partition(table, f"""
let
    Source = Csv.Document(File.Contents(DataFolder & "{fname}"), [Delimiter=",", Columns={len(cols)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{{types}}}, "en-US")
in
    #"Changed Type"
""")

def table(name, cols, partition, measures="", extra_header=(), calc_cols=()):
    out = [f"table {q(name)}"] + [f"\t{e}" for e in extra_header] + [f"\tlineageTag: {uid()}", "", ""]
    out = "\n".join(out) + measures
    for cname, dtype, *rest in cols:
        opts = rest[0] if rest else {}
        out += column(cname, dtype, opts.get("fmt"), opts.get("sum", "none"), opts.get("extra", ()))
    for cname, dtype, expr in calc_cols:
        out += column(cname, dtype, expr=expr)
    out += partition + "\tannotation PBI_ResultType = Table\n\n"
    write(f"{SM}/definition/tables/{name}.tmdl", out)

HIDDEN = ("isHidden",)
MONEY, MONEY_VAR = "\\$#,0", "\\$#,0;(\\$#,0);\\$#,0"
PCT_VAR = "+0.0%;-0.0%;0.0%"

sales_cols = [("Order ID", "int64", {"fmt": "0"}), ("Order Date", "dateTime", {"fmt": "Short Date", "extra": HIDDEN}),
              ("Customer ID", "int64", {"fmt": "0", "extra": HIDDEN}), ("Product ID", "int64", {"fmt": "0", "extra": HIDDEN}),
              ("Quantity", "int64", {"fmt": "#,0", "sum": "sum"}),
              ("Unit Price", "double", {"fmt": "\\$#,0.00"}), ("Discount", "double", {"fmt": "0%"})]
sales_measures = "".join([
    measure("Total Sales", "SUMX ( Sales, Sales[Quantity] * Sales[Unit Price] * ( 1 - Sales[Discount] ) )", MONEY, "Revenue"),
    measure("Total Cost", "SUMX ( Sales, Sales[Quantity] * RELATED ( Products[Unit Cost] ) )", MONEY, "Revenue"),
    measure("Gross Profit", "[Total Sales] - [Total Cost]", MONEY, "Revenue"),
    measure("Profit Margin %", "DIVIDE ( [Gross Profit], [Total Sales] )", "0.0%", "Revenue"),
    measure("Orders", "DISTINCTCOUNT ( Sales[Order ID] )", "#,0", "Volume"),
    measure("Units Sold", "SUM ( Sales[Quantity] )", "#,0", "Volume"),
    measure("Avg Order Value", "DIVIDE ( [Total Sales], [Orders] )", MONEY, "Volume"),
    measure("Avg Selling Price", "DIVIDE ( [Total Sales], [Units Sold] )", "\\$#,0.00", "Volume"),
    measure("Sales PY", "CALCULATE ( [Total Sales], SAMEPERIODLASTYEAR ( 'Calendar'[Date] ) )", MONEY, "Time Intelligence"),
    measure("Sales YoY %", "DIVIDE ( [Total Sales] - [Sales PY], [Sales PY] )", PCT_VAR, "Time Intelligence"),
])
table("Sales", sales_cols, csv_partition("Sales", "Sales.csv", sales_cols), sales_measures)

# Price/volume split, product by product, of Actual vs the selected version over the months
# that have actuals. Volume = (actual units - plan units) x plan price;
# Price = (actual price - plan price) x actual units. Together they equal the sales variance.
PVM_VARS = """
VAR ActualUnits = [Units Sold]
VAR ActualSales = [Total Sales]
VAR PlanUnits = [Comparison Units YTD]
VAR PlanSales = [Comparison Sales YTD]
VAR PlanPrice = IF ( PlanUnits > 0, PlanSales / PlanUnits, DIVIDE ( ActualSales, ActualUnits ) )"""

def pvm(ret):
    body = "\n".join("    " + line for line in (PVM_VARS.strip("\n") + "\nRETURN\n    " + ret).split("\n"))
    return f"SUMX (\n    VALUES ( Products[Product ID] ),\n{body}\n)"

def version_sales(v):
    return f'CALCULATE ( SUM ( Plan[Sales] ), Scenario[Scenario] = "{v}" )'

plan_measures = "".join([
    measure("Selected Version", 'SELECTEDVALUE ( Scenario[Scenario], "Budget" )', folder="Comparison"),
    measure("Comparison Sales", """
VAR SelectedVersion = [Selected Version]
RETURN
    CALCULATE ( SUM ( Plan[Sales] ), Scenario[Scenario] = SelectedVersion )""", MONEY, "Comparison"),
    measure("Comparison Units", """
VAR SelectedVersion = [Selected Version]
RETURN
    CALCULATE ( SUM ( Plan[Units] ), Scenario[Scenario] = SelectedVersion )""", "#,0", "Comparison"),
    measure("Comparison Sales YTD",
            "CALCULATE ( [Comparison Sales], KEEPFILTERS ( 'Calendar'[Period Type] = \"Actual\" ) )", MONEY, "Comparison"),
    measure("Comparison Units YTD",
            "CALCULATE ( [Comparison Units], KEEPFILTERS ( 'Calendar'[Period Type] = \"Actual\" ) )", "#,0", "Comparison"),
    measure("Sales Variance", "[Total Sales] - [Comparison Sales YTD]", MONEY_VAR, "Variance"),
    measure("Sales Variance %", "DIVIDE ( [Sales Variance], [Comparison Sales YTD] )", PCT_VAR, "Variance"),
    measure("Volume Variance", pvm("( ActualUnits - PlanUnits ) * PlanPrice"), MONEY_VAR, "Variance"),
    measure("Price Variance", pvm("IF ( ActualUnits > 0, ActualSales - ActualUnits * PlanPrice )"), MONEY_VAR, "Variance"),
    measure("Bridge Value", """
SWITCH (
    SELECTEDVALUE ( 'Variance Bridge'[Sort Order] ),
    1, [Comparison Sales YTD],
    2, [Volume Variance],
    3, [Price Variance]
)""", MONEY_VAR, "Variance"),
    measure("Budget Sales", version_sales("Budget"), MONEY, "Versions"),
    measure("Q1 Forecast Sales", version_sales("Q1 Forecast"), MONEY, "Versions"),
    measure("Q2 Forecast Sales", version_sales("Q2 Forecast"), MONEY, "Versions"),
    measure("Latest Estimate Sales", version_sales("Latest Estimate"), MONEY, "Versions"),
    measure("LE vs Budget", "[Latest Estimate Sales] - [Budget Sales]", MONEY_VAR, "Versions"),
    measure("LE vs Budget %", "DIVIDE ( [LE vs Budget], [Budget Sales] )", PCT_VAR, "Versions"),
])
plan_cols = [("Scenario", "string", {"extra": HIDDEN}), ("Month", "dateTime", {"fmt": "Short Date", "extra": HIDDEN}),
             ("Product ID", "int64", {"fmt": "0", "extra": HIDDEN}), ("Region", "string", {"extra": HIDDEN}),
             ("Units", "int64", {"fmt": "#,0", "sum": "sum"}), ("Sales", "double", {"fmt": MONEY, "sum": "sum"})]
table("Plan", plan_cols, csv_partition("Plan", "Plan.csv", plan_cols), plan_measures)

product_cols = [("Product ID", "int64", {"fmt": "0", "extra": HIDDEN}), ("Product", "string"),
                ("Category", "string"), ("Unit Price", "double", {"fmt": "\\$#,0.00"}),
                ("Unit Cost", "double", {"fmt": "\\$#,0.00"})]
table("Products", product_cols, csv_partition("Products", "Products.csv", product_cols))

customer_cols = [("Customer ID", "int64", {"fmt": "0", "extra": HIDDEN}), ("Customer", "string"),
                 ("Segment", "string"), ("Region", "string", {"extra": HIDDEN}),
                 ("Country", "string", {"extra": ("dataCategory: Country",)})]
table("Customers", customer_cols, csv_partition("Customers", "Customers.csv", customer_cols))

region_cols = [("Region", "string")]
table("Regions", region_cols, csv_partition("Regions", "Regions.csv", region_cols))

cal_cols = [("Date", "dateTime", {"fmt": "Short Date", "extra": ("isKey",)}),
            ("Year", "int64", {"fmt": "0"}),
            ("Quarter", "string"),
            ("Month Number", "int64", {"fmt": "0", "extra": HIDDEN}),
            ("Month", "string", {"extra": ("sortByColumn: 'Month Number'",)}),
            ("Year Month", "string")]
table("Calendar", cal_cols, m_partition("Calendar", """
let
    StartDate = #date(2025, 1, 1),
    EndDate = #date(2026, 12, 31),
    Dates = List.Dates(StartDate, Duration.Days(EndDate - StartDate) + 1, #duration(1, 0, 0, 0)),
    AsTable = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
    Typed = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),
    AddYear = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),
    AddQuarter = Table.AddColumn(AddYear, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text),
    AddMonthNumber = Table.AddColumn(AddQuarter, "Month Number", each Date.Month([Date]), Int64.Type),
    AddMonth = Table.AddColumn(AddMonthNumber, "Month", each Date.ToText([Date], "MMM", "en-US"), type text),
    AddYearMonth = Table.AddColumn(AddMonth, "Year Month", each Date.ToText([Date], "yyyy-MM", "en-US"), type text)
in
    AddYearMonth
"""), extra_header=("dataCategory: Time",),
      calc_cols=[("Period Type", "string",
                  "IF ( 'Calendar'[Date] <= MAX ( Sales[Order Date] ), \"Actual\", \"Forecast\" )")])

versions_m = ", ".join(f'{{"{v}", {o}}}' for v, o, _ in VERSIONS)
table("Scenario", [("Scenario", "string", {"extra": ("sortByColumn: 'Sort Order'",)}),
                   ("Sort Order", "int64", {"fmt": "0", "extra": HIDDEN})],
      m_partition("Scenario", f"""
let
    Source = #table(type table [Scenario = text, #"Sort Order" = Int64.Type], {{{versions_m}}})
in
    Source
"""))

table("Variance Bridge", [("Step", "string", {"extra": ("sortByColumn: 'Sort Order'",)}),
                          ("Sort Order", "int64", {"fmt": "0", "extra": HIDDEN})],
      m_partition("Variance Bridge", """
let
    Source = #table(type table [Step = text, #"Sort Order" = Int64.Type], {{"Comparison version", 1}, {"Volume variance", 2}, {"Price variance", 3}})
in
    Source
"""))

rels = [("Sales.'Order Date'", "Calendar.Date"), ("Sales.'Product ID'", "Products.'Product ID'"),
        ("Sales.'Customer ID'", "Customers.'Customer ID'"), ("Customers.Region", "Regions.Region"),
        ("Plan.Month", "Calendar.Date"), ("Plan.'Product ID'", "Products.'Product ID'"),
        ("Plan.Region", "Regions.Region"), ("Plan.Scenario", "Scenario.Scenario")]
write(f"{SM}/definition/relationships.tmdl",
      "".join(f"relationship {uid()}\n\tfromColumn: {a}\n\ttoColumn: {b}\n\n" for a, b in rels))

# ------------------------------------------------------------------ report
RP = f"{NAME}.Report"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report"
V_VISUAL, V_PAGE, V_REPORT = "2.2.0", "2.0.0", "3.0.0"
wjson(f"{RP}/.platform", platform("Report"))
wjson(f"{RP}/definition.pbir", {
    "$schema": f"{SCHEMA}/definitionProperties/2.0.0/schema.json",
    "version": "4.0",
    "datasetReference": {"byPath": {"path": f"../{SM}"}},
})
wjson(f"{RP}/definition/version.json", {
    "$schema": f"{SCHEMA}/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})

THEME = "SalesTheme.json"
wjson(f"{RP}/StaticResources/RegisteredResources/{THEME}", {
    "name": "Sales Theme",
    "dataColors": ["#2563EB", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6", "#06B6D4", "#EC4899", "#84CC16"],
    "background": "#FFFFFF", "foreground": "#1F2937", "tableAccent": "#2563EB",
    "good": "#10B981", "bad": "#EF4444", "neutral": "#F59E0B",
    "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#1F2937"}},
    "visualStyles": {"page": {"*": {"background": [{"color": {"solid": {"color": "#F3F4F6"}}, "transparency": 0}]}},
                     "waterfallChart": {"*": {"sentimentColors": [{"increaseFill": {"solid": {"color": "#10B981"}},
                                                                   "decreaseFill": {"solid": {"color": "#EF4444"}},
                                                                   "totalFill": {"solid": {"color": "#2563EB"}}}]}},
                     "*": {"*": {"border": [{"show": True, "color": {"solid": {"color": "#E5E7EB"}}, "radius": 8}],
                                 "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
                                 "dropShadow": [{"show": False}]}}},
})
wjson(f"{RP}/definition/report.json", {
    "$schema": f"{SCHEMA}/definition/report/{V_REPORT}/schema.json",
    "themeCollection": {"customTheme": {"name": THEME, "type": "RegisteredResources",
                                        "reportVersionAtImport": {"visual": V_VISUAL, "report": V_REPORT, "page": V_PAGE}}},
    "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                          "items": [{"name": THEME, "path": THEME, "type": "CustomTheme"}]}],
    "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                 "allowChangeFilterTypes": True, "useEnhancedTooltips": True},
})

def col(entity, prop):
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}

def mea(prop, entity="Sales"):
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}

def pm(prop):
    return mea(prop, "Plan")

def lit(v):
    return {"expr": {"Literal": {"Value": v}}}

def visual(page, name, vtype, pos, roles, title=None, sort=None, objects=None, z=0):
    x, y, w, h = pos
    v = {"visualType": vtype,
         "query": {"queryState": {r: {"projections": p} for r, p in roles.items()}},
         "drillFilterOtherVisuals": True}
    if sort:
        field, direction = sort
        v["query"]["sortDefinition"] = {"sort": [{"field": field["field"], "direction": direction}], "isDefaultSort": True}
    if objects:
        v["objects"] = objects
    if title:
        v["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{title}'")}}]}
    wjson(f"{RP}/definition/pages/{page}/visuals/{name}/visual.json", {
        "$schema": f"{SCHEMA}/definition/visualContainer/{V_VISUAL}/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": v,
    })

def textbox(page, name, pos, text, size="20pt"):
    x, y, w, h = pos
    wjson(f"{RP}/definition/pages/{page}/visuals/{name}/visual.json", {
        "$schema": f"{SCHEMA}/definition/visualContainer/{V_VISUAL}/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0},
        "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": text, "textStyle": {"fontWeight": "bold", "fontSize": size}}]}]}}]},
            "drillFilterOtherVisuals": True},
    })

def year_filter(name, year):
    return {"filters": [{
        "name": name,
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": "Calendar"}}, "Property": "Year"}},
        "type": "Categorical",
        "filter": {"Version": 2,
                   "From": [{"Name": "c", "Entity": "Calendar", "Type": 0}],
                   "Where": [{"Condition": {"In": {
                       "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "Year"}}],
                       "Values": [[{"Literal": {"Value": f"{year}L"}}]]}}}]},
    }]}

def page(name, display, filters=None):
    p = {"$schema": f"{SCHEMA}/definition/page/{V_PAGE}/schema.json",
         "name": name, "displayName": display, "displayOption": "FitToPage", "height": 720, "width": 1280}
    if filters:
        p["filterConfig"] = filters
    wjson(f"{RP}/definition/pages/{name}/page.json", p)

dropdown = {"data": [{"properties": {"mode": lit("'Dropdown'")}}]}
single_dropdown = {**dropdown, "selection": [{"properties": {"singleSelect": lit("true")}}]}

def cards(page_name, y, measures, start_z):
    width = (1232 - 12 * (len(measures) - 1)) / len(measures)
    for i, m in enumerate(measures):
        visual(page_name, f"kpi{i + 1}", "card", (24 + i * (width + 12), y, width, 100), {"Values": [m]}, z=start_z + i)

# Page 1: Overview
P1 = "overview"
page(P1, "Sales Overview")
textbox(P1, "title", (24, 12, 640, 52), "Sales Overview")
visual(P1, "yearSlicer", "slicer", (900, 12, 170, 56), {"Values": [col("Calendar", "Year")]}, objects=dropdown, z=1)
visual(P1, "regionSlicer", "slicer", (1086, 12, 170, 56), {"Values": [col("Regions", "Region")]}, objects=dropdown, z=2)
cards(P1, 80, [mea("Total Sales"), mea("Gross Profit"), mea("Profit Margin %"), mea("Orders"), mea("Sales YoY %")], 3)
visual(P1, "salesTrend", "lineChart", (24, 192, 776, 262),
       {"Category": [col("Calendar", "Year Month")], "Y": [mea("Total Sales"), mea("Sales PY")]},
       title="Monthly Sales vs Prior Year", sort=(col("Calendar", "Year Month"), "Ascending"), z=10)
visual(P1, "segmentDonut", "donutChart", (812, 192, 444, 262),
       {"Category": [col("Customers", "Segment")], "Y": [mea("Total Sales")]}, title="Sales by Customer Segment", z=11)
visual(P1, "categoryColumns", "clusteredColumnChart", (24, 466, 616, 238),
       {"Category": [col("Products", "Category")], "Y": [mea("Total Sales"), mea("Gross Profit")]},
       title="Sales and Profit by Category", sort=(mea("Total Sales"), "Descending"), z=12)
visual(P1, "countryBars", "clusteredBarChart", (652, 466, 604, 238),
       {"Category": [col("Customers", "Country")], "Y": [mea("Total Sales")]},
       title="Sales by Country", sort=(mea("Total Sales"), "Descending"), z=13)

# Page 2: Actual vs selected version, with the price/volume split
P2 = "variance"
page(P2, "Price & Volume Variance", year_filter("yearFilterVariance", PLAN_YEAR))
textbox(P2, "title", (24, 12, 700, 52), f"Actual vs Plan — Price & Volume Variance (FY{PLAN_YEAR} YTD)")
visual(P2, "versionSlicer", "slicer", (900, 12, 170, 56), {"Values": [col("Scenario", "Scenario")]},
       title="Compare to", objects=single_dropdown, z=1)
visual(P2, "regionSlicer", "slicer", (1086, 12, 170, 56), {"Values": [col("Regions", "Region")]}, objects=dropdown, z=2)
cards(P2, 80, [mea("Total Sales"), pm("Comparison Sales YTD"), pm("Sales Variance"), pm("Sales Variance %"),
               pm("Volume Variance"), pm("Price Variance")], 3)
visual(P2, "bridge", "waterfallChart", (24, 192, 520, 262),
       {"Category": [col("Variance Bridge", "Step")], "Y": [pm("Bridge Value")]},
       title="Sales Bridge: Comparison Version to Actual", sort=(col("Variance Bridge", "Step"), "Ascending"), z=10)
visual(P2, "monthlyPvm", "clusteredColumnChart", (24, 466, 520, 238),
       {"Category": [col("Calendar", "Month")], "Y": [pm("Volume Variance"), pm("Price Variance")]},
       title="Volume and Price Variance by Month", sort=(col("Calendar", "Month"), "Ascending"), z=11)
visual(P2, "pvmMatrix", "pivotTable", (556, 192, 700, 512),
       {"Rows": [col("Products", "Category"), col("Products", "Product")],
        "Values": [mea("Units Sold"), pm("Comparison Units YTD"), mea("Total Sales"), pm("Comparison Sales YTD"),
                   pm("Volume Variance"), pm("Price Variance"), pm("Sales Variance")]},
       title="Price & Volume Variance by Product", sort=(pm("Sales Variance"), "Ascending"), z=12)

# Page 3: Full-year version comparison
P3 = "versions"
page(P3, "Budget & Forecasts", year_filter("yearFilterVersions", PLAN_YEAR))
textbox(P3, "title", (24, 12, 900, 52), f"FY{PLAN_YEAR} Budget, Q1 Forecast, Q2 Forecast & Latest Estimate")
visual(P3, "regionSlicer", "slicer", (1086, 12, 170, 56), {"Values": [col("Regions", "Region")]}, objects=dropdown, z=1)
cards(P3, 80, [pm("Budget Sales"), pm("Q1 Forecast Sales"), pm("Q2 Forecast Sales"), pm("Latest Estimate Sales"),
               pm("LE vs Budget"), pm("LE vs Budget %")], 2)
visual(P3, "versionTrend", "lineChart", (24, 192, 776, 262),
       {"Category": [col("Calendar", "Month")],
        "Y": [mea("Total Sales"), pm("Budget Sales"), pm("Q1 Forecast Sales"), pm("Q2 Forecast Sales"),
              pm("Latest Estimate Sales")]},
       title="Monthly Sales: Actual vs Each Version", sort=(col("Calendar", "Month"), "Ascending"), z=10)
visual(P3, "regionBars", "clusteredBarChart", (812, 192, 444, 262),
       {"Category": [col("Regions", "Region")], "Y": [pm("Budget Sales"), pm("Latest Estimate Sales")]},
       title="Budget vs Latest Estimate by Region", sort=(pm("Budget Sales"), "Descending"), z=11)
visual(P3, "versionMatrix", "pivotTable", (24, 466, 1232, 238),
       {"Rows": [col("Products", "Category"), col("Products", "Product")],
        "Values": [pm("Budget Sales"), pm("Q1 Forecast Sales"), pm("Q2 Forecast Sales"), pm("Latest Estimate Sales"),
                   pm("LE vs Budget"), pm("LE vs Budget %")]},
       title="Full-Year Sales by Version", z=12)

# Page 4: Product & customer detail
P4 = "details"
page(P4, "Products & Customers")
textbox(P4, "title", (24, 12, 640, 52), "Products & Customers")
visual(P4, "categorySlicer", "slicer", (900, 12, 170, 56), {"Values": [col("Products", "Category")]}, objects=dropdown, z=1)
visual(P4, "yearSlicer", "slicer", (1086, 12, 170, 56), {"Values": [col("Calendar", "Year")]}, objects=dropdown, z=2)
visual(P4, "productTable", "tableEx", (24, 80, 680, 330),
       {"Values": [col("Products", "Product"), col("Products", "Category"), mea("Units Sold"),
                   mea("Total Sales"), mea("Gross Profit"), mea("Profit Margin %")]},
       title="Product Performance", sort=(mea("Total Sales"), "Descending"), z=3)
visual(P4, "topCustomers", "clusteredBarChart", (716, 80, 540, 330),
       {"Category": [col("Customers", "Customer")], "Y": [mea("Total Sales")]},
       title="Customers by Sales", sort=(mea("Total Sales"), "Descending"), z=4)
visual(P4, "regionMatrix", "pivotTable", (24, 422, 680, 282),
       {"Rows": [col("Regions", "Region"), col("Customers", "Country")],
        "Columns": [col("Calendar", "Year")], "Values": [mea("Total Sales")]},
       title="Sales by Region and Year", z=5)
visual(P4, "quarterColumns", "clusteredColumnChart", (716, 422, 540, 282),
       {"Category": [col("Calendar", "Quarter")], "Series": [col("Calendar", "Year")], "Y": [mea("Total Sales")]},
       title="Quarterly Sales by Year", sort=(col("Calendar", "Quarter"), "Ascending"), z=6)

wjson(f"{RP}/definition/pages/pages.json", {
    "$schema": f"{SCHEMA}/definition/pagesMetadata/1.0.0/schema.json",
    "pageOrder": [P1, P2, P3, P4], "activePageName": P1})

print(f"{len(sales)} sales rows, {len(plan)} plan rows, {len(customers)} customers, {len(products)} products")
