"""Generates the SalesReport Power BI Project (PBIP) into the target directory."""
import csv, json, os, random, sys, uuid
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

# ---------------------------------------------------------------- sample data
products = []
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
pid = 100
for cat, items in catalog.items():
    for name, price, cost in items:
        pid += 1
        products.append({"Product ID": pid, "Product": name, "Category": cat,
                         "Unit Price": price, "Unit Cost": cost})

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
            used.add(n); break
    region = random.choices(list(regions), weights=[5, 4, 3])[0]
    customers.append({"Customer ID": 1000 + i, "Customer": n,
                      "Segment": random.choices(segments, weights=[5, 3, 2])[0],
                      "Region": region, "Country": random.choice(regions[region])})

sales = []
start, end = date(2024, 1, 1), date(2025, 12, 31)
order_id = 50000
d = start
while d <= end:
    seasonal = 1.0 + 0.45 * (d.month in (4, 5, 6, 7, 8)) + 0.3 * (d.month in (11, 12))
    growth = 1.0 + 0.18 * (d.year - 2024)
    for _ in range(max(0, int(random.gauss(4.0 * seasonal * growth, 1.5)))):
        order_id += 1
        cust = random.choice(customers)
        for _ in range(random.choice([1, 1, 1, 2, 2, 3])):
            p = random.choices(products, weights=[3 if p["Category"] == "Bikes" else 6 for p in products])[0]
            qty = random.randint(1, 2) if p["Category"] == "Bikes" else random.randint(1, 6)
            if cust["Segment"] == "Enterprise":
                qty *= 3
            sales.append({"Order ID": order_id, "Order Date": d.isoformat(), "Customer ID": cust["Customer ID"],
                          "Product ID": p["Product ID"], "Quantity": qty, "Unit Price": p["Unit Price"],
                          "Discount": random.choice([0, 0, 0, 0, 0.05, 0.1, 0.15])})
    d += timedelta(days=1)

for fname, rows in [("Products.csv", products), ("Customers.csv", customers), ("Sales.csv", sales)]:
    full = os.path.join(OUT, "data", fname)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

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

TABLES = ["Sales", "Products", "Customers", "Calendar"]
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
      + "".join(f"ref table {t}\n" for t in TABLES) + "\n")

write(f"{SM}/definition/expressions.tmdl",
      'expression DataFolder = "C:\\PowerBI\\SalesReport\\data\\" '
      'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
      f"\tlineageTag: {uid()}\n\n"
      "\tannotation PBI_NavigationStepName = Navigation\n\n"
      "\tannotation PBI_ResultType = Text\n\n")

TYPES = {"int64": "Int64.Type", "double": "type number", "string": "type text", "dateTime": "type date"}

def column(name, dtype, fmt=None, summarize="none", extra=()):
    lines = [f"\tcolumn {q(name)}", f"\t\tdataType: {dtype}"]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    lines += [f"\t\tlineageTag: {uid()}", f"\t\tsummarizeBy: {summarize}", f"\t\tsourceColumn: {name}"]
    lines += [f"\t\t{e}" for e in extra]
    lines += ["", "\t\tannotation SummarizationSetBy = Automatic", "", ""]
    return "\n".join(lines)

def q(name):
    return f"'{name}'" if any(c in name for c in " .-%") or name in ("Date",) else name

def measure(name, expr, fmt, folder=None):
    lines = [f"\tmeasure {q(name)} = {expr}", f"\t\tformatString: {fmt}"]
    if folder:
        lines.append(f"\t\tdisplayFolder: {folder}")
    lines += [f"\t\tlineageTag: {uid()}", "", ""]
    return "\n".join(lines)

def m_partition(table, body):
    expr = "\n".join("\t\t\t\t" + line for line in body.strip("\n").split("\n"))
    return f"\tpartition {table} = m\n\t\tmode: import\n\t\tsource =\n{expr}\n\n"

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

def table(name, cols, partition, measures="", extra_header=()):
    out = [f"table {name}"] + [f"\t{e}" for e in extra_header] + [f"\tlineageTag: {uid()}", "", ""]
    out = "\n".join(out) + measures
    for c in cols:
        cname, dtype, *rest = c
        opts = rest[0] if rest else {}
        out += column(cname, dtype, opts.get("fmt"), opts.get("sum", "none"), opts.get("extra", ()))
    out += partition + "\tannotation PBI_ResultType = Table\n\n"
    write(f"{SM}/definition/tables/{name}.tmdl", out)

sales_cols = [("Order ID", "int64", {"fmt": "0"}), ("Order Date", "dateTime", {"fmt": "Short Date"}),
              ("Customer ID", "int64", {"fmt": "0"}), ("Product ID", "int64", {"fmt": "0"}),
              ("Quantity", "int64", {"fmt": "#,0", "sum": "sum"}),
              ("Unit Price", "double", {"fmt": "\\$#,0.00", "sum": "none"}),
              ("Discount", "double", {"fmt": "0%", "sum": "none"})]
measures = "".join([
    measure("Total Sales", "SUMX ( Sales, Sales[Quantity] * Sales[Unit Price] * ( 1 - Sales[Discount] ) )", "\\$#,0", "Revenue"),
    measure("Total Cost", "SUMX ( Sales, Sales[Quantity] * RELATED ( Products[Unit Cost] ) )", "\\$#,0", "Revenue"),
    measure("Gross Profit", "[Total Sales] - [Total Cost]", "\\$#,0", "Revenue"),
    measure("Profit Margin %", "DIVIDE ( [Gross Profit], [Total Sales] )", "0.0%", "Revenue"),
    measure("Orders", "DISTINCTCOUNT ( Sales[Order ID] )", "#,0", "Volume"),
    measure("Units Sold", "SUM ( Sales[Quantity] )", "#,0", "Volume"),
    measure("Avg Order Value", "DIVIDE ( [Total Sales], [Orders] )", "\\$#,0", "Volume"),
    measure("Sales PY", "CALCULATE ( [Total Sales], SAMEPERIODLASTYEAR ( 'Calendar'[Date] ) )", "\\$#,0", "Time Intelligence"),
    measure("Sales YoY %", "DIVIDE ( [Total Sales] - [Sales PY], [Sales PY] )", "+0.0%;-0.0%;0.0%", "Time Intelligence"),
])
hidden = {"extra": ("isHidden",)}
sales_cols = [(c, t, {**o, **hidden}) if c in ("Customer ID", "Product ID", "Order Date") else (c, t, o)
              for c, t, o in sales_cols]
table("Sales", sales_cols, csv_partition("Sales", "Sales.csv", sales_cols), measures)

product_cols = [("Product ID", "int64", {"fmt": "0", "extra": ("isHidden",)}), ("Product", "string"),
                ("Category", "string"), ("Unit Price", "double", {"fmt": "\\$#,0.00"}),
                ("Unit Cost", "double", {"fmt": "\\$#,0.00"})]
table("Products", product_cols, csv_partition("Products", "Products.csv", product_cols))

customer_cols = [("Customer ID", "int64", {"fmt": "0", "extra": ("isHidden",)}), ("Customer", "string"),
                 ("Segment", "string"), ("Region", "string"),
                 ("Country", "string", {"extra": ("dataCategory: Country",)})]
table("Customers", customer_cols, csv_partition("Customers", "Customers.csv", customer_cols))

cal_cols = [("Date", "dateTime", {"fmt": "Short Date", "extra": ("isKey",)}),
            ("Year", "int64", {"fmt": "0"}),
            ("Quarter", "string"),
            ("Month Number", "int64", {"fmt": "0", "extra": ("isHidden",)}),
            ("Month", "string", {"extra": ("sortByColumn: 'Month Number'",)}),
            ("Year Month", "string")]
table("Calendar", cal_cols, m_partition("Calendar", """
let
    StartDate = #date(2024, 1, 1),
    EndDate = #date(2025, 12, 31),
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
"""), extra_header=("dataCategory: Time",))

rels = [("Sales.'Order Date'", "Calendar.Date"), ("Sales.'Product ID'", "Products.'Product ID'"),
        ("Sales.'Customer ID'", "Customers.'Customer ID'")]
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

def page(name, display):
    wjson(f"{RP}/definition/pages/{name}/page.json", {
        "$schema": f"{SCHEMA}/definition/page/{V_PAGE}/schema.json",
        "name": name, "displayName": display, "displayOption": "FitToPage", "height": 720, "width": 1280})

dropdown = {"data": [{"properties": {"mode": lit("'Dropdown'")}}]}

# Page 1: Overview
P1 = "overview"
page(P1, "Sales Overview")
textbox(P1, "title", (24, 12, 640, 52), "Sales Overview")
visual(P1, "yearSlicer", "slicer", (900, 12, 170, 56), {"Values": [col("Calendar", "Year")]}, objects=dropdown, z=1)
visual(P1, "regionSlicer", "slicer", (1086, 12, 170, 56), {"Values": [col("Customers", "Region")]}, objects=dropdown, z=2)
for i, m in enumerate(["Total Sales", "Gross Profit", "Profit Margin %", "Orders", "Sales YoY %"]):
    visual(P1, f"kpi{i + 1}", "card", (24 + i * 248, 80, 236, 110), {"Values": [mea(m)]}, z=3 + i)
visual(P1, "salesTrend", "lineChart", (24, 204, 776, 250),
       {"Category": [col("Calendar", "Year Month")], "Y": [mea("Total Sales"), mea("Sales PY")]},
       title="Monthly Sales vs Prior Year", sort=(col("Calendar", "Year Month"), "Ascending"), z=10)
visual(P1, "segmentDonut", "donutChart", (812, 204, 444, 250),
       {"Category": [col("Customers", "Segment")], "Y": [mea("Total Sales")]}, title="Sales by Customer Segment", z=11)
visual(P1, "categoryColumns", "clusteredColumnChart", (24, 466, 616, 238),
       {"Category": [col("Products", "Category")], "Y": [mea("Total Sales"), mea("Gross Profit")]},
       title="Sales and Profit by Category", sort=(mea("Total Sales"), "Descending"), z=12)
visual(P1, "countryBars", "clusteredBarChart", (652, 466, 604, 238),
       {"Category": [col("Customers", "Country")], "Y": [mea("Total Sales")]},
       title="Sales by Country", sort=(mea("Total Sales"), "Descending"), z=13)

# Page 2: Product & Customer detail
P2 = "details"
page(P2, "Products & Customers")
textbox(P2, "title", (24, 12, 640, 52), "Products & Customers")
visual(P2, "categorySlicer", "slicer", (900, 12, 170, 56), {"Values": [col("Products", "Category")]}, objects=dropdown, z=1)
visual(P2, "yearSlicer", "slicer", (1086, 12, 170, 56), {"Values": [col("Calendar", "Year")]}, objects=dropdown, z=2)
visual(P2, "productTable", "tableEx", (24, 80, 680, 330),
       {"Values": [col("Products", "Product"), col("Products", "Category"), mea("Units Sold"),
                   mea("Total Sales"), mea("Gross Profit"), mea("Profit Margin %")]},
       title="Product Performance", sort=(mea("Total Sales"), "Descending"), z=3)
visual(P2, "topCustomers", "clusteredBarChart", (716, 80, 540, 330),
       {"Category": [col("Customers", "Customer")], "Y": [mea("Total Sales")]},
       title="Customers by Sales", sort=(mea("Total Sales"), "Descending"), z=4)
visual(P2, "regionMatrix", "pivotTable", (24, 422, 680, 282),
       {"Rows": [col("Customers", "Region"), col("Customers", "Country")],
        "Columns": [col("Calendar", "Year")], "Values": [mea("Total Sales")]},
       title="Sales by Region and Year", z=5)
visual(P2, "quarterColumns", "clusteredColumnChart", (716, 422, 540, 282),
       {"Category": [col("Calendar", "Quarter")], "Series": [col("Calendar", "Year")], "Y": [mea("Total Sales")]},
       title="Quarterly Sales by Year", sort=(col("Calendar", "Quarter"), "Ascending"), z=6)

wjson(f"{RP}/definition/pages/pages.json", {
    "$schema": f"{SCHEMA}/definition/pagesMetadata/1.0.0/schema.json",
    "pageOrder": [P1, P2], "activePageName": P1})

print(f"{len(sales)} sales rows, {len(customers)} customers, {len(products)} products")
