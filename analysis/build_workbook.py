"""Build report/Shepparton_United_vs_Echuca_2026.xlsx from the scraped CSVs in data/.

Run from the repo root:  python3 analysis/build_workbook.py
Every comparison cell is an Excel formula over the data sheets, so the workbook recalculates if data changes.
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as col

DATA = Path("data")
OUT = Path("report/Shepparton_United_vs_Echuca_2026.xlsx")
UNITED, ECHUCA = "Shepparton United", "Echuca"

FONT = "Arial"
NAVY, WHITE = "1F2A44", "FFFFFF"
HDR_FILL = PatternFill("solid", fgColor=NAVY)
UNITED_FILL = PatternFill("solid", fgColor="DCE9FA")   # light blue
ECHUCA_FILL = PatternFill("solid", fgColor="E3F2E1")   # light green
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Border(bottom=Side(style="thin", color="D9D9D9"))

# Stat codes used by Premier Data. Checked against the long-name "Season Stats" table where possible.
GLOSSARY = {
    "D": "Disposals", "K": "Kicks", "HB": "Handballs", "CP": "Contested possessions", "TGB": "Total groundball gets",
    "HBG": "Hard ball gets", "LBG": "Loose ball gets", "IP": "Intercept possessions", "GTH": "Gathers",
    "HR": "Handball receives", "M": "Marks", "CM": "Contested marks", "UM": "Uncontested marks", "IM": "Intercept marks",
    "MI50": "Marks inside 50", "RP": "Ranking points (Premier Data impact score)", "HO": "Hit outs",
    "HOA": "Hit outs to advantage", "Cl": "Clearances", "CC": "Centre clearances", "BUC": "Ball-up clearances",
    "TIC": "Throw-in clearances", "I50": "Inside 50s", "R50": "Rebound 50s", "FF": "Frees for", "FA": "Frees against",
    "KI": "Kick-ins", "1%": "One-percenters", "TO": "Turnovers", "BTO": "Back-half turnovers",
    "MTO": "Midfield turnovers", "FTO": "Forward-half turnovers", "PR": "Overall pressure", "PRA": "Pressure acts",
    "PRF": "Pressure acts forward", "Ch": "Chases", "Sm": "Smothers", "Sp": "Spoils", "T": "Tackles",
    "TE": "Tackle efficiency", "FTKL": "Forward 50 tackles", "MTKL": "Midfield tackles", "BTKL": "Back 50 tackles",
    "G": "Goals", "B": "Behinds", "RB": "Rushed behinds", "SE%": "Scoring efficiency %", "SS": "Scoring shots",
    "GA%": "Goal accuracy %", "DE%": "Disposal efficiency %", "I50%": "Inside-50 efficiency %",
    "K%": "Kick efficiency %", "H%": "Handball efficiency %", "C%": "Clearance efficiency %",
    "R50%": "Rebound-50 efficiency %", "KI%": "Kick-in efficiency %", "KE": "Effective kicks",
    "HE": "Effective handballs", "ED": "Effective disposals", "EFFC": "Effective clearances",
    "EFFR": "Effective rebound 50s", "SI": "Score involvements", "GA": "Goal assists", "BOU": "Bounces",
    "GST": "GST (code not labelled by Premier Data)", "KO": "KO (code not labelled by Premier Data)",
}
# Direction: Y = higher is better, N = lower is better, ? = no clear good/bad direction.
LOWER_BETTER = {"FA", "TO", "BTO", "MTO", "FTO", "RB"}
NO_DIRECTION = {"B", "R50", "KI", "HR", "GST", "KO", "BOU", "HO"}


def direction(code):
    return "N" if code in LOWER_BETTER else "?" if code in NO_DIRECTION else "Y"


def num(df, skip):
    for c in df.columns:
        if c not in skip:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
    return df


def style_header(ws, row, ncols, height=30):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, color=WHITE, size=10)
        cell.fill = HDR_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = height


def set_font(ws):
    for row in ws.iter_rows():
        for cell in row:
            if cell.font is None or cell.font.name != FONT:
                cell.font = Font(name=FONT, size=10, bold=cell.font.bold if cell.font else False,
                                 color=cell.font.color if cell.font else None, italic=cell.font.italic if cell.font else False)


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = Font(name=FONT, bold=True, size=14, color=NAVY)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(name=FONT, italic=True, size=10, color="595959")


def write_table(ws, df, start_row, highlight=None, fmt="0.0", header_comments=None):
    """Write a DataFrame with a styled header; returns (first_data_row, last_data_row)."""
    for j, h in enumerate(df.columns, 1):
        ws.cell(row=start_row, column=j, value=h)
        if header_comments and h in header_comments:
            ws.cell(row=start_row, column=j).comment = Comment(header_comments[h], "Premier Data")
    style_header(ws, start_row, len(df.columns))
    for i, rec in enumerate(df.itertuples(index=False), start_row + 1):
        for j, v in enumerate(rec, 1):
            if isinstance(v, float) and pd.isna(v):
                v = None
            c = ws.cell(row=i, column=j, value=v)
            c.font = Font(name=FONT, size=10)
            c.border = THIN
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                c.number_format = fmt
        if highlight:
            fill = highlight(rec)
            if fill:
                for j in range(1, len(df.columns) + 1):
                    ws.cell(row=i, column=j).fill = fill
    return start_row + 1, start_row + len(df)


def team_fill(rec):
    name = rec[0] if isinstance(rec[0], str) else ""
    return UNITED_FILL if name == UNITED else ECHUCA_FILL if name == ECHUCA else None


wb = Workbook()

# ------------------------------------------------------------------ data sheets
per_game = num(pd.read_csv(DATA / "leaders_teams_averages.csv"), skip=("Name",)).drop(columns=["Rank"]).rename(columns={"Name": "Team"})
totals = num(pd.read_csv(DATA / "leaders_teams_totals.csv"), skip=("Name",)).drop(columns=["Rank"]).rename(columns={"Name": "Team"})
# Drop columns that are 0 for every club (not recorded in this competition).
empty = [c for c in per_game.columns[2:] if per_game[c].abs().sum() == 0]
per_game = per_game.drop(columns=empty)
totals = totals.drop(columns=[c for c in empty if c in totals.columns])
codes_comment = {c: GLOSSARY.get(c, c) for c in per_game.columns}

ws_pg = wb.active
ws_pg.title = "League Per Game"
title(ws_pg, "All 12 GVL clubs: per-game averages, 2026 season (including finals)",
      "Source: Premier Data Leaderboards > Teams > Averages. Percent columns are whole-number percentages (69 = 69%). Hover a header for its full name.")
pg_first, pg_last = write_table(ws_pg, per_game, 4, highlight=team_fill, header_comments=codes_comment)
PG_HDR_ROW = 4
pg_col = {h: col(j) for j, h in enumerate(per_game.columns, 1)}

ws_tot = wb.create_sheet("League Season Totals")
title(ws_tot, "All 12 GVL clubs: season totals, 2026 (including finals)",
      "Source: Premier Data Leaderboards > Teams > Totals. Finals teams played more games, so compare per-game averages for fairness.")
write_table(ws_tot, totals, 4, highlight=team_fill, fmt="#,##0", header_comments=codes_comment)
# Percentage columns in the totals view are season percentages, not sums.
for j, h in enumerate(totals.columns, 1):
    if h.endswith("%"):
        for r in range(5, 5 + len(totals)):
            ws_tot.cell(row=r, column=j).number_format = "0.0"

# ------------------------------------------------------------------ per-game sheets (for / against / diff)
game_sheets = {}
for team, prefix, short in [(UNITED, "", "United"), (ECHUCA, "echuca_", "Echuca")]:
    f = num(pd.read_csv(DATA / f"{prefix}team_match_stats_for.csv", dtype=str), skip=("Opponent", "Round", "Result"))
    a = num(pd.read_csv(DATA / f"{prefix}team_match_stats_against.csv", dtype=str), skip=("Opponent", "Round", "Result"))
    for d in (f, a):
        d["Round"] = d.Round.apply(lambda r: int(r) if r.isdigit() else r)
        d.insert(2, "Stage", d.Round.apply(lambda r: "Home & away" if isinstance(r, int) else "Finals"))
    stats = list(f.columns[4:])
    names = {}
    for kind, df, note in [("For", f, f"{team}'s own stats in each game"),
                           ("Against", a, f"The opponent's stats in each game against {team}")]:
        ws = wb.create_sheet(f"{short} Games {kind}")
        title(ws, f"{team} 2026: {note}", "Source: Premier Data Team Summary > Match Statistics. Hover a header for its full name.")
        write_table(ws, df, 4, fmt="0", header_comments=codes_comment)
        ws.freeze_panes = "E5"
        names[kind] = ws.title
    # Differential sheet = For minus Against, as formulas.
    ws = wb.create_sheet(f"{short} Games Diff")
    title(ws, f"{team} 2026: differential in each game (own stat minus opponent's stat)",
          "Formulas: For sheet minus Against sheet. Positive = more than the opponent.")
    hdr = list(f.columns)
    for j, h in enumerate(hdr, 1):
        ws.cell(row=4, column=j, value=h)
        if h in codes_comment:
            ws.cell(row=4, column=j).comment = Comment(codes_comment[h], "Premier Data")
    style_header(ws, 4, len(hdr))
    fs, as_ = f"'{names['For']}'", f"'{names['Against']}'"
    for i in range(len(f)):
        r = 5 + i
        for j, h in enumerate(hdr, 1):
            L = col(j)
            ws.cell(row=r, column=j, value=f"={fs}!{L}{r}" if j <= 4 else f"={fs}!{L}{r}-{as_}!{L}{r}")
            ws.cell(row=r, column=j).font = Font(name=FONT, size=10)
            ws.cell(row=r, column=j).border = THIN
            if j > 4:
                ws.cell(row=r, column=j).number_format = "0;-0;0"
    last = 4 + len(f)
    ws.conditional_formatting.add(f"E5:{col(len(hdr))}{last}", CellIsRule(operator="greaterThan", formula=["0"], font=Font(color="1F6FC5")))
    ws.conditional_formatting.add(f"E5:{col(len(hdr))}{last}", CellIsRule(operator="lessThan", formula=["0"], font=Font(color="C0392B")))
    ws.freeze_panes = "E5"
    game_sheets[team] = dict(for_=names["For"], against=names["Against"], diff=ws.title, stats=stats, n=len(f),
                             opps=sorted(f.Opponent.unique()), hdr=hdr, df=f)

# ------------------------------------------------------------------ by-opponent matrices
opp_sheets = {}
for team, short in [(UNITED, "United"), (ECHUCA, "Echuca")]:
    g = game_sheets[team]
    ws = wb.create_sheet(f"{short} vs Each Opponent")
    title(ws, f"{team}: average stats against each opponent (all 2026 games including finals)",
          "Three blocks: own average, opponent's average, and the difference. Blue = better than the opponent, red = worse "
          "(uses the 'Higher is better?' setting; '?' stats are not shaded).")
    first_col_hdr = ["Stat", "Stat name", "Higher is better?"]
    blocks = [("Own average", g["for_"]), ("Opponent average", g["against"]), ("Difference (own - opponent)", None)]
    opps = g["opps"]
    last_row_games = 4 + g["n"]
    # Row 4: block titles; row 5: headers
    c0 = len(first_col_hdr) + 1
    for b, (bname, _) in enumerate(blocks):
        start = c0 + b * (len(opps) + 1)
        ws.cell(row=4, column=start, value=bname).font = Font(name=FONT, bold=True, color=NAVY)
    hdr = first_col_hdr[:]
    for b in range(len(blocks)):
        hdr += opps + [""]
    for j, h in enumerate(hdr, 1):
        ws.cell(row=5, column=j, value=h if h else None)
    style_header(ws, 5, len(hdr), height=45)
    count_row = 6
    ws.cell(row=count_row, column=2, value="Games played vs this opponent").font = Font(name=FONT, italic=True, size=10)
    for k, opp in enumerate(opps):
        cc = col(c0 + k)
        ws[f"{cc}{count_row}"] = f"=COUNTIF('{g['for_']}'!$A$5:$A${last_row_games},{cc}$5)"
        ws[f"{cc}{count_row}"].font = Font(name=FONT, italic=True, size=10)
    for i, s in enumerate(g["stats"]):
        r = 7 + i
        sc = col(g["hdr"].index(s) + 1)
        ws.cell(row=r, column=1, value=s)
        ws.cell(row=r, column=2, value=GLOSSARY.get(s, s))
        dcell = ws.cell(row=r, column=3, value=direction(s))
        dcell.fill = INPUT_FILL
        dcell.font = Font(name=FONT, size=10, color="0000FF")
        dcell.alignment = Alignment(horizontal="center")
        for b, (bname, sheet) in enumerate(blocks):
            for k, opp in enumerate(opps):
                cidx = c0 + b * (len(opps) + 1) + k
                oc = col(c0 + k)  # opponent names live in the first block's header cells
                if sheet:
                    f_ = (f"=AVERAGEIF('{sheet}'!$A$5:$A${last_row_games},{oc}$5,"
                          f"'{sheet}'!{sc}$5:{sc}${last_row_games})")
                else:
                    own = col(c0 + k)
                    opp_c = col(c0 + (len(opps) + 1) + k)
                    f_ = f"={own}{r}-{opp_c}{r}"
                cell = ws.cell(row=r, column=cidx, value=f_)
                cell.number_format = "0.0;-0.0;0.0"
                cell.font = Font(name=FONT, size=10)
                cell.border = THIN
        ws.cell(row=r, column=1).font = Font(name=FONT, size=10, bold=True)
        ws.cell(row=r, column=2).font = Font(name=FONT, size=10)
    last = 6 + len(g["stats"])
    dstart = c0 + 2 * (len(opps) + 1)
    rng = f"{col(dstart)}7:{col(dstart + len(opps) - 1)}{last}"
    tl = f"{col(dstart)}7"
    # Direction-aware shading: blue = better than the opponent, red = worse.
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND($C7="Y",{tl}>0)'], fill=PatternFill("solid", fgColor="CFE2F8"), stopIfTrue=True))
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND($C7="Y",{tl}<0)'], fill=PatternFill("solid", fgColor="F8D5D0"), stopIfTrue=True))
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND($C7="N",{tl}<0)'], fill=PatternFill("solid", fgColor="CFE2F8"), stopIfTrue=True))
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND($C7="N",{tl}>0)'], fill=PatternFill("solid", fgColor="F8D5D0"), stopIfTrue=True))
    ws.freeze_panes = "D7"
    ws.column_dimensions["A"].width = 7
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 10
    for j in range(4, len(hdr) + 1):
        ws.column_dimensions[col(j)].width = 11
    opp_sheets[team] = ws.title

# ------------------------------------------------------------------ season for-vs-against comparison
def season_table(prefix):
    s = pd.read_csv(DATA / f"{prefix}team_season_for_vs_against.csv")
    s = num(s, skip=("Stat Type",))
    # Rows 52-81 of the source table (0-based 51..80 here) are the "score sources" section; label them.
    labels, seen = [], {}
    for idx, name in enumerate(s["Stat Type"]):
        section = "Score sources" if 51 <= idx + 1 <= 81 else "General"
        key = (name, section)
        seen[key] = seen.get(key, 0) + 1
        suffix = f" ({seen[key]})" if seen[key] > 1 else ""
        labels.append((section, f"{name}{suffix}"))
    s["Section"] = [l[0] for l in labels]
    s["Label"] = [l[1] for l in labels]
    return s


su, se = season_table(""), season_table("echuca_")
assert list(su.Label) == list(se.Label)
ws = wb.create_sheet("Season For v Against")
title(ws, "Season averages: each club vs its own opponents (United 18 games; Echuca 21 games incl. finals)",
      "Source: Premier Data Team Summary > Season Stats (All Opponents). Differences are formulas. "
      "Column J = how much bigger Echuca's edge over its opponents is than United's (direction-adjusted: positive = Echuca's edge is better).")
hdr = ["Section", "Stat", "Higher is better?", f"{UNITED} for", f"{UNITED} against", f"{UNITED} difference",
       f"{ECHUCA} for", f"{ECHUCA} against", f"{ECHUCA} difference", "Echuca edge minus United edge"]
for j, h in enumerate(hdr, 1):
    ws.cell(row=4, column=j, value=h)
style_header(ws, 4, len(hdr), height=45)


def season_dir(section, name):
    n = name.lower()
    if section == "Score sources":
        return "?"
    if "turnover" in n or n.startswith("rushed") or "frees against" in n:
        return "N"
    if n in {"behinds", "kick ins", "hit outs", "handball receives", "rebound 50s", "effective rebound 50s"}:
        return "?"
    return "Y"


for i, (_, ru) in enumerate(su.iterrows()):
    r = 5 + i
    re_ = se.iloc[i]
    ws.cell(row=r, column=1, value=ru.Section)
    ws.cell(row=r, column=2, value=ru.Label)
    d = ws.cell(row=r, column=3, value=season_dir(ru.Section, ru.Label))
    d.fill, d.font, d.alignment = INPUT_FILL, Font(name=FONT, size=10, color="0000FF"), Alignment(horizontal="center")
    ws.cell(row=r, column=4, value=float(ru.For))
    ws.cell(row=r, column=5, value=float(ru.Against))
    ws.cell(row=r, column=6, value=f"=D{r}-E{r}")
    ws.cell(row=r, column=7, value=float(re_.For))
    ws.cell(row=r, column=8, value=float(re_.Against))
    ws.cell(row=r, column=9, value=f"=G{r}-H{r}")
    ws.cell(row=r, column=10, value=f'=IF(C{r}="?","",IF(C{r}="N",-1,1)*(I{r}-F{r}))')
    for j in range(1, 11):
        c = ws.cell(row=r, column=j)
        if j not in (3,):
            c.font = Font(name=FONT, size=10)
        c.border = THIN
        if j >= 4:
            c.number_format = "0.0;-0.0;0.0"
    ws.cell(row=r, column=4).fill = ws.cell(row=r, column=5).fill = ws.cell(row=r, column=6).fill = UNITED_FILL
    ws.cell(row=r, column=7).fill = ws.cell(row=r, column=8).fill = ws.cell(row=r, column=9).fill = ECHUCA_FILL
season_last = 4 + len(su)
ws.conditional_formatting.add(f"J5:J{season_last}", ColorScaleRule(start_type="num", start_value=-10, start_color="CFE2F8",
                                                                   mid_type="num", mid_value=0, mid_color="FFFFFF",
                                                                   end_type="num", end_value=10, end_color="F4B183"))
ws.freeze_panes = "C5"
for L, w in zip("ABCDEFGHIJ", [14, 34, 10, 14, 14, 14, 14, 14, 14, 16]):
    ws.column_dimensions[L].width = w
ws.auto_filter.ref = f"A4:J{season_last}"

# ------------------------------------------------------------------ WHERE TO IMPROVE (front sheet)
wi = wb.create_sheet("Where to Improve", 0)
title(wi, "Where Shepparton United needs to improve to play like the premiers (Echuca)",
      "Per-game averages from the 'League Per Game' sheet. Every number below is a formula. Rows are ordered by the size of the gap "
      "(biggest Echuca advantage first) as at 25 Sep 2026.")
wi["A3"] = "Priority threshold (gap in standard deviations):"
wi["A3"].font = Font(name=FONT, bold=True, size=10)
wi["F3"] = 0.75
wi["F3"].fill, wi["F3"].font = INPUT_FILL, Font(name=FONT, size=10, color="0000FF", bold=True)
wi["F3"].comment = Comment("Editable. A gap bigger than this many standard deviations (the typical spread between the 12 clubs) is flagged as a priority.", "Workbook")
wi["G3"] = "← editable. Yellow cells with blue text are settings you can change."
wi["G3"].font = Font(name=FONT, italic=True, size=9, color="595959")

hdr = ["Stat", "Stat name", "Higher is better?", "United per game", "Echuca per game", "League average",
       "Gap (Echuca − United)", "Gap as % of United", "United rank (of 12)", "Echuca rank (of 12)",
       "Gap in std devs (+ = Echuca better)", "Verdict"]
HR = 5
for j, h in enumerate(hdr, 1):
    wi.cell(row=HR, column=j, value=h)
style_header(wi, HR, len(hdr), height=45)

pg_sheet = "'League Per Game'"
team_rng = f"{pg_sheet}!$A${pg_first}:$A${pg_last}"
stat_cols = [c for c in per_game.columns[2:]]


def pg_range(c):
    L = pg_col[c]
    return f"{pg_sheet}!${L}${pg_first}:${L}${pg_last}"


# Order rows by the (Python-computed) direction-adjusted gap so the biggest Echuca advantages sit on top.
pgi = per_game.set_index("Team")
order = []
for c in stat_cols:
    dirn = direction(c)
    sd = pgi[c].std(ddof=0)
    gap = (pgi.loc[ECHUCA, c] - pgi.loc[UNITED, c]) / sd if sd else 0
    key = -999 if dirn == "?" else (gap if dirn == "Y" else -gap)
    order.append((key, c))
order = [c for _, c in sorted(order, reverse=True)]

for i, c in enumerate(order):
    r = HR + 1 + i
    rng = pg_range(c)
    wi.cell(row=r, column=1, value=c)
    wi.cell(row=r, column=2, value=GLOSSARY.get(c, c))
    d = wi.cell(row=r, column=3, value=direction(c))
    d.fill, d.font, d.alignment = INPUT_FILL, Font(name=FONT, size=10, color="0000FF"), Alignment(horizontal="center")
    wi.cell(row=r, column=4, value=f'=INDEX({rng},MATCH("{UNITED}",{team_rng},0))')
    wi.cell(row=r, column=5, value=f'=INDEX({rng},MATCH("{ECHUCA}",{team_rng},0))')
    wi.cell(row=r, column=6, value=f"=AVERAGE({rng})")
    wi.cell(row=r, column=7, value=f"=E{r}-D{r}")
    wi.cell(row=r, column=8, value=f"=IF(D{r}=0,\"\",G{r}/D{r})")
    wi.cell(row=r, column=9, value=f'=IF(C{r}="N",RANK(D{r},{rng},1),RANK(D{r},{rng},0))')
    wi.cell(row=r, column=10, value=f'=IF(C{r}="N",RANK(E{r},{rng},1),RANK(E{r},{rng},0))')
    wi.cell(row=r, column=11, value=f'=IF(OR(C{r}="?",STDEVP({rng})=0),"",IF(C{r}="N",-1,1)*G{r}/STDEVP({rng}))')
    wi.cell(row=r, column=12, value=(f'=IF(K{r}="","Context only (no clear better direction)",'
                                     f'IF(K{r}>=$F$3,"PRIORITY: Echuca well ahead",'
                                     f'IF(K{r}>0,"Echuca ahead",IF(K{r}<=-$F$3,"United strength","United ahead or level"))))'))
    for j in range(1, 13):
        cell = wi.cell(row=r, column=j)
        if j != 3:
            cell.font = Font(name=FONT, size=10, bold=(j == 1))
        cell.border = THIN
    for j in (4, 5, 6, 7):
        wi.cell(row=r, column=j).number_format = "0.0;-0.0;0.0"
    wi.cell(row=r, column=8).number_format = "0%;-0%;0%"
    wi.cell(row=r, column=11).number_format = "0.00;-0.00;0.00"
    wi.cell(row=r, column=4).fill = UNITED_FILL
    wi.cell(row=r, column=5).fill = ECHUCA_FILL
wi_last = HR + len(order)
wi.conditional_formatting.add(f"K{HR+1}:K{wi_last}", ColorScaleRule(start_type="num", start_value=-2, start_color="CFE2F8",
                                                                    mid_type="num", mid_value=0, mid_color="FFFFFF",
                                                                    end_type="num", end_value=2, end_color="F4B183"))
wi.conditional_formatting.add(f"L{HR+1}:L{wi_last}", FormulaRule(formula=[f'LEFT(L{HR+1},8)="PRIORITY"'],
                                                                 font=Font(bold=True, color="C0392B")))
wi.freeze_panes = f"C{HR+1}"
wi.auto_filter.ref = f"A{HR}:L{wi_last}"
for L, w in zip("ABCDEFGHIJKL", [8, 34, 10, 11, 11, 11, 12, 11, 11, 11, 13, 38]):
    wi.column_dimensions[L].width = w

# Head-to-head block beneath the table: United's two games against Echuca.
h2h_row = wi_last + 3
wi.cell(row=h2h_row, column=1, value="Head to head: United vs Echuca in 2026").font = Font(name=FONT, bold=True, size=12, color=NAVY)
ug = game_sheets[UNITED]
key_stats = ["D", "CP", "Cl", "I50", "MI50", "M", "T", "PRA", "PR", "TO", "SS", "G", "RP"]
rows_vs = [i for i, o in enumerate(ug["df"].Opponent) if o == ECHUCA]
r0 = h2h_row + 1
for j, h in enumerate(["Round", "Side"] + [GLOSSARY.get(s, s) for s in key_stats], 1):
    wi.cell(row=r0, column=j, value=h)
style_header(wi, r0, 2 + len(key_stats), height=45)
rr = r0 + 1
for gi in rows_vs:
    src_row = 5 + gi
    for side, sheet in [("United", ug["for_"]), ("Echuca", ug["against"]), ("Difference", None)]:
        wi.cell(row=rr, column=1, value=f"='{ug['for_']}'!B{src_row}")
        wi.cell(row=rr, column=2, value=side)
        for k, s in enumerate(key_stats):
            L = col(ug["hdr"].index(s) + 1)
            v = f"='{sheet}'!{L}{src_row}" if sheet else f"={col(3 + k)}{rr-2}-{col(3 + k)}{rr-1}"
            c = wi.cell(row=rr, column=3 + k, value=v)
            c.number_format = "0;-0;0"
        for j in range(1, 3 + len(key_stats)):
            c = wi.cell(row=rr, column=j)
            c.font = Font(name=FONT, size=10, bold=(side == "Difference"))
            c.border = THIN
            if side == "United":
                c.fill = UNITED_FILL
            elif side == "Echuca":
                c.fill = ECHUCA_FILL
        rr += 1
wi.cell(row=rr, column=1, value="United lost these games by 37 points (Round 6) and 100 points (Round 17). Positive difference = United had more.").font = Font(name=FONT, italic=True, size=9, color="595959")

# ------------------------------------------------------------------ READ ME
rm = wb.create_sheet("Read Me", 0)
title(rm, "Shepparton United vs Echuca (2026 premiers): team stats workbook")
lines = [
    ("Where to Improve", "START HERE. Every stat: United vs Echuca vs league average per game, the gap, both clubs' league rank, and a verdict. Biggest Echuca advantages are at the top."),
    ("Season For v Against", "Each club's season averages against its own opponents. Shows how much each club out-did (or was out-done by) the teams it played."),
    ("United vs Each Opponent", "United's average stats against every opponent: own average, opponent's average and the difference."),
    ("Echuca vs Each Opponent", "The same for Echuca, so you can compare how the premiers handled each club."),
    ("United Games For / Against / Diff", "Every United game: United's stats, the opponent's stats, and the difference (formulas)."),
    ("Echuca Games For / Against / Diff", "Every Echuca game including their three finals."),
    ("League Per Game", "All 12 clubs' per-game averages (the base for 'Where to Improve'). United = blue row, Echuca = green row."),
    ("League Season Totals", "All 12 clubs' season totals. Finals teams played more games, so per-game is the fairer comparison."),
]
rm["A3"] = "Sheet"
rm["B3"] = "What it shows"
style_header(rm, 3, 2)
for i, (a, b) in enumerate(lines, 4):
    rm.cell(row=i, column=1, value=a).font = Font(name=FONT, bold=True, size=10)
    rm.cell(row=i, column=2, value=b).font = Font(name=FONT, size=10)
    rm.cell(row=i, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    rm.cell(row=i, column=1).alignment = Alignment(vertical="top")
n = 4 + len(lines) + 1
notes = [
    "How to read it",
    "• 'Higher is better?' (yellow, blue text) says whether a bigger number is good (Y), bad (N, e.g. turnovers), or has no clear direction (?). You can change these; verdicts and shading update.",
    "• 'Gap in std devs' puts every stat on the same scale: 1.0 means the gap is as big as the typical spread between the 12 clubs. Above the threshold on 'Where to Improve' (0.75 by default) = PRIORITY.",
    "• Blue shading = United better, orange/red = Echuca (or the opponent) better.",
    "",
    "Data notes",
    "• Source: Premier Data (pdapp2.advancedhp.com.au), Shepparton United club account, scraped 25 Sep 2026. Season complete; Echuca won the grand final.",
    "• United played 18 games (no finals). Echuca's figures include 3 finals, which were against the strongest teams.",
    "• 'Pressure acts' (PRA) and 'Overall pressure' (PR) are different Premier Data measures; both are included.",
    "• Stats recorded as 0 for every club (frees against, bounces, KO) are left out of the league sheets.",
    "• 'Score sources' rows in 'Season For v Against' are Premier Data's scoring breakdown by source (e.g. scores from turnovers); the direction is left as '?'.",
    "• Stat codes GST and KO are not labelled by Premier Data.",
]
for i, t in enumerate(notes):
    c = rm.cell(row=n + i, column=1 if not t.startswith("•") else 2, value=t)
    c.font = Font(name=FONT, size=10, bold=not t.startswith("•"), color=NAVY if not t.startswith("•") else None)
    if t.startswith("•"):
        c.alignment = Alignment(wrap_text=True, vertical="top")
g_row = n + len(notes) + 1
rm.cell(row=g_row, column=1, value="Stat codes").font = Font(name=FONT, bold=True, size=10, color=NAVY)
for i, (k, v) in enumerate(sorted(GLOSSARY.items()), g_row + 1):
    rm.cell(row=i, column=1, value=k).font = Font(name=FONT, bold=True, size=10)
    rm.cell(row=i, column=2, value=v).font = Font(name=FONT, size=10)
rm.column_dimensions["A"].width = 30
rm.column_dimensions["B"].width = 120

# Widths for data sheets
for ws in wb.worksheets:
    if ws.title in ("League Per Game", "League Season Totals"):
        ws.column_dimensions["A"].width = 20
        for j in range(2, ws.max_column + 1):
            ws.column_dimensions[col(j)].width = 8
        ws.freeze_panes = "B5"
    elif "Games" in ws.title:
        ws.column_dimensions["A"].width = 18
        for j in range(2, ws.max_column + 1):
            ws.column_dimensions[col(j)].width = 7 if j > 4 else 11
    ws.sheet_view.showGridLines = ws.title in ("League Per Game", "League Season Totals") or "Games" in ws.title

# Tab colours
for ws in wb.worksheets:
    ws.sheet_properties.tabColor = "1F6FC5" if "United" in ws.title else "3A8F3A" if "Echuca" in ws.title else NAVY

wb.save(OUT)
print("saved", OUT)
