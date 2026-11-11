"""Builds share-portfolio-tracker.xlsx — a formula-driven share portfolio model."""
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import BarChart, Reference
from openpyxl.comments import Comment

FONT = "Arial"
BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
INPUT_FILL = PatternFill("solid", fgColor="FFFF99")
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
TOTAL_FILL = PatternFill("solid", fgColor="D9E1F2")
thin = Side(style="thin", color="BFBFBF")
BOX = Border(top=thin, bottom=thin, left=thin, right=thin)

CUR = '$#,##0.00;($#,##0.00);-'
CUR0 = '$#,##0;($#,##0);-'
PCT = '0.0%;(0.0%);-'
UNITS = '#,##0;(#,##0);-'
DATEF = 'dd-mmm-yyyy'

N_TICKERS = 20          # rows available on Prices / Portfolio
TX_ROWS = 500           # rows available on Transactions / Dividends
TX_FIRST, TX_LAST = 5, 5 + TX_ROWS - 1
IMP_ROWS = 1000         # rows available on CommSec Import
IM_FIRST, IM_LAST = 6, 6 + IMP_ROWS - 1
IMP = "'CommSec Import'"
P_FIRST = 5             # first ticker row on Prices
PF_FIRST = 7            # first holding row on Portfolio
PF_LAST = PF_FIRST + N_TICKERS - 1
PF_TOTAL = PF_LAST + 1


def franking_formula(r):
    fk = f"INDEX(Prices!$E${P_FIRST}:$E${P_FIRST + N_TICKERS - 1},MATCH(B{r},Prices!$A${P_FIRST}:$A${P_FIRST + N_TICKERS - 1},0))"
    return (f'=IF(OR(B{r}="",E{r}=""),"",ROUND(E{r}*IFERROR({fk},0)*Prices!$H$5/(1-Prices!$H$5),2))')


def f(color=BLACK, bold=False, size=10, italic=False):
    return Font(name=FONT, color=color, bold=bold, size=size, italic=italic)


def title(ws, text, sub):
    ws["A1"] = text
    ws["A1"].font = Font(name=FONT, bold=True, size=14, color="1F3864")
    ws["A2"] = sub
    ws["A2"].font = f(italic=True, color="595959")


def header(ws, row, labels, widths=None):
    for i, lab in enumerate(labels, 1):
        c = ws.cell(row=row, column=i, value=lab)
        c.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        c.fill = HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 32
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w


def add_charts(wb, n):
    """(Re)draw the Summary charts for the first n holdings."""
    s, pf = wb["Summary"], wb["Portfolio"]
    s._charts = []
    ch = BarChart()
    ch.type = "col"; ch.title = "Cost vs Market Value by Holding"
    ch.y_axis.title = "$"; ch.y_axis.numFmt = '$#,##0'
    ch.y_axis.majorGridlines = None
    data = Reference(pf, min_col=8, max_col=8, min_row=6, max_row=PF_FIRST + max(n, 1) - 1)
    data2 = Reference(pf, min_col=10, max_col=10, min_row=6, max_row=PF_FIRST + max(n, 1) - 1)
    cats = Reference(pf, min_col=1, min_row=PF_FIRST, max_row=PF_FIRST + max(n, 1) - 1)
    ch.add_data(data, titles_from_data=True); ch.add_data(data2, titles_from_data=True)
    ch.set_categories(cats)
    ch.series[0].graphicalProperties.solidFill = "A6A6A6"
    ch.series[1].graphicalProperties.solidFill = "1F3864"
    ch.height, ch.width = 8, 16
    s.add_chart(ch, "D14")

    ch2 = BarChart()
    ch2.type = "col"; ch2.grouping = "stacked"; ch2.overlap = 100
    ch2.title = "Capital vs Dividend Return by Holding"
    ch2.y_axis.numFmt = '$#,##0'; ch2.y_axis.majorGridlines = None
    for col, color in ((15, "1F3864"), (16, "70AD47")):
        ch2.add_data(Reference(pf, min_col=col, min_row=6, max_row=PF_FIRST + max(n, 1) - 1),
                     titles_from_data=True)
    ch2.set_categories(cats)
    ch2.series[0].graphicalProperties.solidFill = "1F3864"
    ch2.series[1].graphicalProperties.solidFill = "70AD47"
    ch2.height, ch2.width = 8, 16
    s.add_chart(ch2, "D31")



def build_workbook():
    wb = Workbook()

    # ---------------------------------------------------------------- Guide
    g = wb.active
    g.title = "Guide"
    title(g, "Share Portfolio Tracker", "How to use this workbook")
    g.column_dimensions["A"].width = 24
    g.column_dimensions["B"].width = 95
    rows = [
        ("Automatic refresh", "Save your CommSec CSV export(s) into the 'CommSec Exports' folder, close this workbook and double-click 'Refresh Portfolio.bat'. It imports your trades, downloads current prices and dividend history (Yahoo Finance, which carries ASX data), works out the dividends you were entitled to and fills the sheets below. See SETUP.md for the one-off install."),
        ("Step 1 – Prices", "Filled by the refresh. Set each share's Franking % once (e.g. 100% for CBA). You can still type prices manually if you prefer."),
        ("Step 2 – Trades", "EITHER paste your CommSec CSV export into 'CommSec Import' (recommended) OR type trades into 'Transactions'. Don't enter the same trade in both – it will be counted twice."),
        ("Step 3 – Dividends", "Filled by the refresh: for each dividend, units held on the ex-dividend date × dividend per share. Add anything it can't see (e.g. special or unlisted payments) as Source = Manual."),
        ("Step 4 – Review", "Portfolio shows each holding; Summary shows the whole portfolio, capital vs dividend returns, and dividends by year."),
        ("", ""),
        ("Colour key", ""),
        ("Blue text, yellow fill", "Inputs – the only cells you should type into."),
        ("Black text", "Formulas – calculated automatically, do not overwrite."),
        ("Green text", "Links pulled from another sheet."),
        ("", ""),
        ("Definitions", ""),
        ("Units held", "Units bought − units sold."),
        ("Cost", "Total cost of units still held = units held × average cost per unit (incl. brokerage)."),
        ("Value", "Units held × current price."),
        ("Unrealised gain/loss", "Value − cost of units still held (paper gain/loss)."),
        ("Realised gain/loss", "Net sale proceeds − (units sold × average cost per unit)."),
        ("Capital return", "Unrealised + realised gain/loss."),
        ("Dividend return", "Cash dividends received."),
        ("Total return", "Capital return + dividend return."),
        ("Return %", "Each return ÷ total amount invested in that share (all buys incl. brokerage)."),
        ("", ""),
        ("Assumptions", ""),
        ("Cost method", "Average cost: average cost per unit = all buy costs (incl. brokerage) ÷ all units bought. Brokerage on sells reduces sale proceeds."),
        ("Not tax advice", "Realised gains here are for tracking only. Tax rules (e.g. CGT discounts, specific-parcel matching) may differ – check with your accountant."),
        ("CommSec import", "In CommSec: Portfolio > Accounts > Transactions, choose the date range (go back to your first purchase), download as CSV. Open the CSV, copy all rows including the header, and paste into cell A5 of 'CommSec Import'. Lines starting 'B ' (buy) or 'S ' (sell) become trades; cash transfers etc. are ignored. Brokerage is worked out from the Debit/Credit amount."),
        ("Check column", "Every trade row on 'CommSec Import' shows a Status. 'Add XYZ to Prices' means that ticker is missing from the Prices sheet – add it and its price or it won't appear in Portfolio. The Summary sheet warns you if any rows need attention."),
        ("Dividend rules", "Entitlement uses the CommSec date as the settlement date: units count if they settled by the day after the ex-date (i.e. bought before the ex-date under T+2). DRP shares aren't in CommSec exports – add each DRP allotment as a Buy on 'Transactions' (brokerage 0) so later dividends count them. Auto rows are dated on the ex-date, not the pay date."),
        ("Franking", "Franking credits = cash dividend × Franking % × tax rate ÷ (1 − tax rate). Yahoo doesn't publish franking, so it uses the % you set per share – check it against your dividend statements."),
        ("Example data", "The first refresh deletes all example rows automatically. If you're entering data by hand instead, delete the example trades and dividends yourself. The example rows (CBA, BHP, VAS, WES) and their prices are illustrative only – delete or overwrite them with your own."),
        ("Capacity", f"{N_TICKERS} shares, {TX_ROWS} manual transactions, {IMP_ROWS} CommSec import rows and {TX_ROWS} dividend rows. To add more shares, extend the Prices list and copy a Portfolio row down."),
    ]
    for i, (a, b) in enumerate(rows, 4):
        g.cell(row=i, column=1, value=a).font = f(bold=True)
        g.cell(row=i, column=2, value=b).font = f()
        g.cell(row=i, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        if a in ("Colour key", "Definitions", "Assumptions"):
            g.cell(row=i, column=1).font = f(bold=True, size=11, color="1F3864")
    g["A10"].font = f(color=BLUE, bold=True); g["A10"].fill = INPUT_FILL
    g["A12"].font = f(color=GREEN, bold=True)

    # ---------------------------------------------------------------- Prices
    p = wb.create_sheet("Prices")
    title(p, "Share Prices", "Filled automatically by 'Refresh Portfolio' – or type prices yourself (inputs in blue / yellow)")
    header(p, 4, ["Ticker", "Company / Fund Name", "Current Price ($)", "Price Date",
                  "Franking %", "Yahoo Code\n(optional)"], [12, 34, 18, 16, 12, 14])
    p.column_dimensions["G"].width = 3
    p.column_dimensions["H"].width = 26
    for r_, lab, val, fmt in ((4, "Company tax rate", 0.30, PCT), (7, "Last refreshed", None, 'dd-mmm-yyyy hh:mm'),
                              (10, "Contains example data", "Yes", None)):
        p.cell(row=r_, column=8, value=lab).font = f(bold=True)
        c = p.cell(row=r_ + 1, column=8, value=val)
        c.font = f(BLUE if r_ == 4 else BLACK); c.border = BOX
        if r_ == 4: c.fill = INPUT_FILL
        if fmt: c.number_format = fmt
    p["H5"].comment = Comment("Used to gross up franking credits: credit = cash × franking% × rate ÷ (1 − rate). "
                              "30% is the standard Australian company tax rate.", "Model")
    p["E4"].comment = Comment("How much of this share's dividends are usually franked (e.g. 100% for CBA). "
                              "Set once per share; applied to every dividend for that share.", "Model")
    p["F4"].comment = Comment("Leave blank – the refresh uses TICKER.AX on Yahoo Finance. "
                              "Only fill in if a share has a different Yahoo code.", "Model")
    examples = [("CBA", "Commonwealth Bank", 165.00, 1.0), ("BHP", "BHP Group", 42.50, 1.0),
                ("VAS", "Vanguard Australian Shares ETF", 105.20, 0.7), ("WES", "Wesfarmers", 80.10, 1.0)]
    for i in range(N_TICKERS):
        r = P_FIRST + i
        for col, fmt in ((1, None), (2, None), (3, CUR), (4, DATEF), (5, '0%'), (6, None)):
            c = p.cell(row=r, column=col)
            c.font = f(BLUE); c.fill = INPUT_FILL; c.border = BOX
            if fmt: c.number_format = fmt
        if i < len(examples):
            t, n, px, fk = examples[i]
            p.cell(row=r, column=5, value=fk)
            p.cell(row=r, column=1, value=t); p.cell(row=r, column=2, value=n)
            p.cell(row=r, column=3, value=px); p.cell(row=r, column=4, value=date(2026, 11, 10))
    p["C5"].comment = Comment("Example price only – replace with the actual latest price.", "Model")
    p.freeze_panes = "A5"
    TICKER_LIST = f"Prices!$A${P_FIRST}:$A${P_FIRST + N_TICKERS - 1}"

    # ---------------------------------------------------------------- Transactions
    t = wb.create_sheet("Transactions")
    title(t, "Transactions", "Record every buy and sell. Net amount = cost for buys, proceeds for sells")
    header(t, 4, ["Date", "Ticker", "Type\n(Buy/Sell)", "Units", "Price per Unit ($)",
                  "Brokerage ($)", "Net Amount ($)", "Notes"], [14, 10, 11, 10, 15, 13, 16, 30])
    dv_type = DataValidation(type="list", formula1='"Buy,Sell"', allow_blank=True)
    dv_tick = DataValidation(type="list", formula1=f"={TICKER_LIST}", allow_blank=True)
    t.add_data_validation(dv_type); t.add_data_validation(dv_tick)
    dv_type.add(f"C{TX_FIRST}:C{TX_LAST}"); dv_tick.add(f"B{TX_FIRST}:B{TX_LAST}")
    tx_examples = [
        (date(2024, 2, 12), "CBA", "Buy", 100, 118.40, 19.95),
        (date(2024, 3, 4), "BHP", "Buy", 300, 44.10, 19.95),
        (date(2024, 6, 18), "VAS", "Buy", 200, 94.60, 19.95),
        (date(2024, 9, 9), "BHP", "Buy", 200, 41.80, 19.95),
        (date(2025, 1, 20), "WES", "Buy", 150, 70.25, 19.95),
        (date(2025, 8, 14), "CBA", "Sell", 40, 172.30, 19.95),
        (date(2025, 10, 2), "VAS", "Buy", 100, 101.50, 19.95),
    ]
    for i in range(TX_ROWS):
        r = TX_FIRST + i
        for col, fmt in ((1, DATEF), (2, None), (3, None), (4, UNITS), (5, CUR), (6, CUR), (8, None)):
            c = t.cell(row=r, column=col)
            c.font = f(BLUE); c.fill = INPUT_FILL; c.border = BOX
            if fmt: c.number_format = fmt
        if i < len(tx_examples):
            for col, v in enumerate(tx_examples[i], 1):
                t.cell(row=r, column=col, value=v)
        c = t.cell(row=r, column=7,
                   value=f'=IF(OR(B{r}="",D{r}=""),"",IF(C{r}="Sell",D{r}*E{r}-F{r},D{r}*E{r}+F{r}))')
        c.font = f(); c.number_format = CUR; c.border = BOX
    for r_ in range(TX_FIRST, TX_FIRST + len(tx_examples)):
        t.cell(row=r_, column=8, value="Example – removed on first refresh")
    t.freeze_panes = "A5"

    # ---------------------------------------------------------------- CommSec Import
    im = wb.create_sheet("CommSec Import")
    title(im, "CommSec Import", "Paste your CommSec Transactions CSV (all rows incl. header) into cell A5. Columns H–N are calculated.")
    im["A3"] = "Paste area (A–F)  →"
    im["A3"].font = f(BLUE, bold=True)
    im["H3"] = "Parsed trades – do not edit"
    im["H3"].font = f(bold=True, color="1F3864")
    header(im, 5, ["Date", "Reference", "Details", "Debit($)", "Credit($)", "Balance($)", "",
                   "Type", "Ticker", "Units", "Price per Unit ($)", "Net Amount ($)", "Brokerage ($)", "Status"],
           [13, 12, 34, 12, 12, 13, 2, 8, 9, 10, 14, 15, 13, 26])
    im.cell(row=5, column=7).fill = PatternFill(None)
    IM_TICKERS = f"Prices!$A${P_FIRST}:$A${P_FIRST + N_TICKERS - 1}"
    for i in range(IMP_ROWS):
        r = IM_FIRST + i
        for col, fmt in ((1, DATEF), (2, None), (3, None), (4, CUR), (5, CUR), (6, CUR)):
            c = im.cell(row=r, column=col)
            c.font = f(BLUE); c.fill = INPUT_FILL
            if fmt: c.number_format = fmt
        D = f"TRIM($C{r})"
        sp = f'FIND(" ",{D},3)'
        at = f'FIND("@",{D})'
        formulas = {
            8: (f'=IF(LEFT({D},2)="B ","Buy",IF(LEFT({D},2)="S ","Sell",""))', None),
            9: (f'=IF($H{r}="","",TRIM(MID({D},{sp}+1,{at}-{sp}-1)))', None),
            10: (f'=IF($H{r}="","",VALUE(MID({D},3,{sp}-3)))', UNITS),
            11: (f'=IF($H{r}="","",VALUE(TRIM(MID({D},{at}+1,50))))', '$#,##0.0000'),
            12: (f'=IF($H{r}="","",IF($H{r}="Buy",ABS(VALUE($D{r})),ABS(VALUE($E{r}))))', CUR),
            13: (f'=IF($H{r}="","",ROUND(IF($H{r}="Buy",L{r}-J{r}*K{r},J{r}*K{r}-L{r}),2))', CUR),
            14: (f'=IF($C{r}="","",IF($H{r}="","Ignored (not a trade)",'
                 f'IF(ISERROR(J{r}+K{r}+L{r}),"Check row – could not read",'
                 f'IF(ISNA(MATCH(I{r},{IM_TICKERS},0)),"Add "&I{r}&" to Prices","OK"))))', None),
        }
        for col, (fm, fmt) in formulas.items():
            c = im.cell(row=r, column=col, value=fm)
            c.font = f(); c.border = BOX
            if fmt: c.number_format = fmt
    im.freeze_panes = "A6"
    IMP_STATUS = f"{IMP}!$N${IM_FIRST}:$N${IM_LAST}"

    # ---------------------------------------------------------------- Dividends
    d = wb.create_sheet("Dividends")
    title(d, "Dividends Received", "Auto rows are filled by 'Refresh Portfolio'. Add your own rows with Source = Manual.")
    header(d, 4, ["Date\n(ex-div date for Auto rows)", "Ticker", "Units Held", "Dividend per Share ($)",
                  "Cash Dividend ($)", "Franking Credits ($)", "Source", "Notes"],
           [16, 10, 11, 16, 16, 16, 12, 34])
    d["F4"].comment = Comment("Calculated from the share's Franking % and the tax rate on the Prices sheet. "
                              "Type over it if you know the exact credit.", "Model")
    d["G4"].comment = Comment("Auto = downloaded by the refresh (rows are rebuilt every refresh). "
                              "Manual = your own entry, never touched. Changing an Auto row to Manual "
                              "keeps your edits and stops the refresh re-adding that dividend.", "Model")
    dv_tick2 = DataValidation(type="list", formula1=f"={TICKER_LIST}", allow_blank=True)
    d.add_data_validation(dv_tick2); dv_tick2.add(f"B{TX_FIRST}:B{TX_LAST}")
    div_examples = [
        (date(2024, 3, 28), "CBA", 100, 2.15),
        (date(2024, 9, 26), "BHP", 300, 1.11),
        (date(2024, 9, 26), "CBA", 100, 2.50),
        (date(2025, 1, 2), "VAS", 200, 0.90),
        (date(2025, 3, 27), "BHP", 500, 0.79),
        (date(2025, 3, 31), "WES", 150, 0.95),
        (date(2025, 9, 29), "CBA", 60, 2.60),
        (date(2025, 10, 2), "WES", 150, 1.11),
        (date(2026, 1, 2), "VAS", 300, 0.95),
    ]
    for i in range(TX_ROWS):
        r = TX_FIRST + i
        for col, fmt in ((1, DATEF), (2, None), (3, UNITS), (4, '$#,##0.0000'), (7, None), (8, None)):
            c = d.cell(row=r, column=col)
            c.font = f(BLUE); c.fill = INPUT_FILL; c.border = BOX
            if fmt: c.number_format = fmt
        if i < len(div_examples):
            dt, tk, u, dps = div_examples[i]
            d.cell(row=r, column=1, value=dt); d.cell(row=r, column=2, value=tk)
            d.cell(row=r, column=3, value=u); d.cell(row=r, column=4, value=dps)
            d.cell(row=r, column=7, value="Example")
        c = d.cell(row=r, column=5, value=f'=IF(OR(B{r}="",C{r}=""),"",C{r}*D{r})')
        c.font = f(); c.number_format = CUR; c.border = BOX
        c = d.cell(row=r, column=6, value=franking_formula(r))
        c.font = f(); c.number_format = CUR; c.border = BOX
    d.freeze_panes = "A5"

    # ---------------------------------------------------------------- Portfolio
    pf = wb.create_sheet("Portfolio")
    title(pf, "Portfolio Holdings", "Per-share view: units, price, cost, value, gains/losses, capital & dividend returns (all calculated)")
    groups = [("A5:B5", "Holding"), ("C5:H5", "Units & Cost"), ("I5:L5", "Price & Value"),
              ("M5:O5", "Capital Return"), ("P5:Q5", "Dividends & Total"), ("R5:U5", "Returns % (on amount invested)")]
    for rng, lab in groups:
        pf.merge_cells(rng)
        c = pf[rng.split(":")[0]]
        c.value = lab; c.font = f(bold=True, color="1F3864"); c.fill = TOTAL_FILL
        c.alignment = Alignment(horizontal="center")
    header(pf, 6, ["Ticker", "Name", "Units Bought", "Units Sold", "Units Held",
                   "Amount Invested ($)\n(all buys)", "Avg Cost per Unit ($)", "Cost of Units Held ($)",
                   "Current Price ($)", "Market Value ($)", "Unrealised Gain/(Loss) ($)", "Unrealised %",
                   "Sale Proceeds ($)", "Realised Gain/(Loss) ($)", "Capital Return ($)",
                   "Dividends Received ($)", "Total Return ($)",
                   "Capital Return %", "Dividend Return %", "Total Return %", "Portfolio Weight %"],
           [10, 30, 10, 10, 10, 15, 13, 15, 12, 15, 15, 11, 14, 14, 14, 14, 14, 11, 11, 11, 11])
    TX = lambda col: f"Transactions!${col}${TX_FIRST}:${col}${TX_LAST}"
    IM = lambda col: f"{IMP}!${col}${IM_FIRST}:${col}${IM_LAST}"
    DV = lambda col: f"Dividends!${col}${TX_FIRST}:${col}${TX_LAST}"
    for i in range(N_TICKERS):
        r = PF_FIRST + i
        pr = P_FIRST + i
        blank = f'IF($A{r}="","",'
        cells = {
            "A": (f'=IF(Prices!A{pr}="","",Prices!A{pr})', None, GREEN),
            "B": (f'=IF(Prices!B{pr}="","",Prices!B{pr})', None, GREEN),
            "C": (f'={blank}SUMIFS({TX("D")},{TX("B")},$A{r},{TX("C")},"Buy")+SUMIFS({IM("J")},{IM("I")},$A{r},{IM("H")},"Buy"))', UNITS, BLACK),
            "D": (f'={blank}SUMIFS({TX("D")},{TX("B")},$A{r},{TX("C")},"Sell")+SUMIFS({IM("J")},{IM("I")},$A{r},{IM("H")},"Sell"))', UNITS, BLACK),
            "E": (f'={blank}C{r}-D{r})', UNITS, BLACK),
            "F": (f'={blank}SUMIFS({TX("G")},{TX("B")},$A{r},{TX("C")},"Buy")+SUMIFS({IM("L")},{IM("I")},$A{r},{IM("H")},"Buy"))', CUR, BLACK),
            "G": (f'={blank}IF(C{r}=0,0,F{r}/C{r}))', CUR, BLACK),
            "H": (f'={blank}E{r}*G{r})', CUR, BLACK),
            "I": (f'=IF($A{r}="","",Prices!C{pr})', CUR, GREEN),
            "J": (f'={blank}E{r}*I{r})', CUR, BLACK),
            "K": (f'={blank}J{r}-H{r})', CUR, BLACK),
            "L": (f'={blank}IF(H{r}=0,0,K{r}/H{r}))', PCT, BLACK),
            "M": (f'={blank}SUMIFS({TX("G")},{TX("B")},$A{r},{TX("C")},"Sell")+SUMIFS({IM("L")},{IM("I")},$A{r},{IM("H")},"Sell"))', CUR, BLACK),
            "N": (f'={blank}M{r}-D{r}*G{r})', CUR, BLACK),
            "O": (f'={blank}K{r}+N{r})', CUR, BLACK),
            "P": (f'={blank}SUMIFS({DV("E")},{DV("B")},$A{r}))', CUR, BLACK),
            "Q": (f'={blank}O{r}+P{r})', CUR, BLACK),
            "R": (f'={blank}IF(F{r}=0,0,O{r}/F{r}))', PCT, BLACK),
            "S": (f'={blank}IF(F{r}=0,0,P{r}/F{r}))', PCT, BLACK),
            "T": (f'={blank}IF(F{r}=0,0,Q{r}/F{r}))', PCT, BLACK),
            "U": (f'={blank}IF($J${PF_TOTAL}=0,0,J{r}/$J${PF_TOTAL}))', PCT, BLACK),
        }
        for col, (formula, fmt, color) in cells.items():
            c = pf[f"{col}{r}"]
            c.value = formula; c.font = f(color); c.border = BOX
            if fmt: c.number_format = fmt
    # totals
    rt = PF_TOTAL
    pf[f"A{rt}"] = "TOTAL"
    sum_cols = ["F", "H", "J", "K", "M", "N", "O", "P", "Q"]
    for col in sum_cols:
        pf[f"{col}{rt}"] = f"=SUM({col}{PF_FIRST}:{col}{PF_LAST})"
        pf[f"{col}{rt}"].number_format = CUR
    pf[f"L{rt}"] = f"=IF(H{rt}=0,0,K{rt}/H{rt})"
    pf[f"R{rt}"] = f"=IF(F{rt}=0,0,O{rt}/F{rt})"
    pf[f"S{rt}"] = f"=IF(F{rt}=0,0,P{rt}/F{rt})"
    pf[f"T{rt}"] = f"=IF(F{rt}=0,0,Q{rt}/F{rt})"
    pf[f"U{rt}"] = f"=SUM(U{PF_FIRST}:U{PF_LAST})"
    for col in ["L", "R", "S", "T", "U"]:
        pf[f"{col}{rt}"].number_format = PCT
    for col in range(1, 22):
        c = pf.cell(row=rt, column=col)
        c.font = f(bold=True); c.fill = TOTAL_FILL; c.border = BOX
    pf.freeze_panes = "C7"

    # ---------------------------------------------------------------- Summary
    s = wb.create_sheet("Summary", 1)
    title(s, "Portfolio Summary", "Whole-portfolio snapshot – everything here is calculated from the other sheets")
    s["A3"] = (f'=IF(COUNTIF({IMP_STATUS},"Add*")+COUNTIF({IMP_STATUS},"Check*")=0,"",'
               f'"⚠ "&(COUNTIF({IMP_STATUS},"Add*")+COUNTIF({IMP_STATUS},"Check*"))'
               f'&" CommSec import row(s) need attention – see Status column on CommSec Import")')
    s["A3"].font = Font(name=FONT, bold=True, color="C00000")
    s.column_dimensions["A"].width = 34
    s.column_dimensions["B"].width = 18
    s.column_dimensions["C"].width = 4
    s.column_dimensions["D"].width = 14
    s.column_dimensions["E"].width = 18
    s.column_dimensions["F"].width = 22
    P = lambda col: f"Portfolio!{col}{PF_TOTAL}"
    kpis = [
        ("Value & Cost", None, None),
        ("Amount invested (all buys)", f"={P('F')}", CUR),
        ("Cost of units still held", f"={P('H')}", CUR),
        ("Current market value", f"={P('J')}", CUR),
        ("", None, None),
        ("Capital Return", None, None),
        ("Unrealised gain/(loss)", f"={P('K')}", CUR),
        ("Unrealised %  (on cost held)", f"={P('L')}", PCT),
        ("Realised gain/(loss)", f"={P('N')}", CUR),
        ("Total capital return", f"={P('O')}", CUR),
        ("Capital return %", f"={P('R')}", PCT),
        ("", None, None),
        ("Dividend Return", None, None),
        ("Cash dividends received", f"={P('P')}", CUR),
        ("Franking / tax credits", f"=SUM(Dividends!F{TX_FIRST}:F{TX_LAST})", CUR),
        ("Dividend return %", f"={P('S')}", PCT),
        ("", None, None),
        ("Total Return", None, None),
        ("Total return (capital + dividends)", f"={P('Q')}", CUR),
        ("Total return %", f"={P('T')}", PCT),
        ("Share of return from capital", f"=IF(B22=0,0,B13/B22)", PCT),
        ("Share of return from dividends", f"=IF(B22=0,0,B17/B22)", PCT),
    ]
    for i, (lab, formula, fmt) in enumerate(kpis, 4):
        a = s.cell(row=i, column=1, value=lab or None)
        if formula is None and lab:
            a.font = f(bold=True, size=11, color="1F3864")
            continue
        a.font = f()
        if formula:
            b = s.cell(row=i, column=2, value=formula)
            b.font = f(GREEN if formula.startswith("=Portfolio") else BLACK, bold=lab.startswith("Total return"))
            b.number_format = fmt; b.border = BOX
            if lab.startswith("Total return"):
                a.font = f(bold=True); b.fill = TOTAL_FILL
    # sanity: rows used in share formulas
    assert kpis[13 - 4][0] == "Total capital return"
    assert kpis[17 - 4][0] == "Cash dividends received"
    assert kpis[22 - 4][0] == "Total return (capital + dividends)"

    # Dividends by year
    s["D4"] = "Dividends by Year"; s["D4"].font = f(bold=True, size=11, color="1F3864")
    for col, lab in zip("DEF", ["Year", "Cash Dividends ($)", "Franking / Tax Credits ($)"]):
        c = s[f"{col}5"]; c.value = lab
        c.font = Font(name=FONT, bold=True, color="FFFFFF"); c.fill = HEAD_FILL; c.border = BOX
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    years = ["2024", "2025", "2026", "2027", "2028"]
    DA = f"Dividends!$A${TX_FIRST}:$A${TX_LAST}"
    for i, y in enumerate(years):
        r = 6 + i
        c = s[f"D{r}"]; c.value = y; c.font = f(BLUE); c.fill = INPUT_FILL; c.border = BOX
        c.alignment = Alignment(horizontal="center")
        for col, src in (("E", "E"), ("F", "F")):
            rng = f"Dividends!${src}${TX_FIRST}:${src}${TX_LAST}"
            c = s[f"{col}{r}"]
            c.value = (f'=SUMIFS({rng},{DA},">="&DATE(VALUE($D{r}),1,1),'
                       f'{DA},"<="&DATE(VALUE($D{r}),12,31))')
            c.font = f(); c.number_format = CUR; c.border = BOX
    rt2 = 6 + len(years)
    s[f"D{rt2}"] = "Total"
    s[f"E{rt2}"] = f"=SUM(E6:E{rt2-1})"
    s[f"F{rt2}"] = f"=SUM(F6:F{rt2-1})"
    for col in "DEF":
        c = s[f"{col}{rt2}"]; c.font = f(bold=True); c.fill = TOTAL_FILL; c.border = BOX
        if col != "D": c.number_format = CUR
    s["D6"].comment = Comment("Calendar years (Jan–Dec). Type any year you want to see.", "Model")

    add_charts(wb, len(examples))
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
    wb.calculation.fullCalcOnLoad = True
    return wb


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "share-portfolio-tracker.xlsx"
    build_workbook().save(out)
    print("saved", out)
