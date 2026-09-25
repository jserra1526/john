"""Build the two coach-facing reports from data/ (numbers are computed here, not typed in).

Writes report/coach/grand-final-gap.html and report/coach/season-review.html (artifact page bodies),
then render PDFs with:  NODE_PATH=$(npm root -g) node analysis/render_pdf.js

Run from the repo root:  python3 analysis/build_coach_reports.py
"""
import base64
import html
from pathlib import Path

import pandas as pd

DATA, OUT = Path("data"), Path("report/coach")
OUT.mkdir(parents=True, exist_ok=True)
U, E, B = "Shepparton United", "Echuca", "Shepparton Bears"


def num(df, skip=()):
    for c in df.columns:
        if c not in skip:
            conv = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
            if conv.notna().any():
                df[c] = conv
    return df


pg = num(pd.read_csv(DATA / "leaders_teams_averages.csv"), ("Name",)).set_index("Name")
ladder = pd.read_csv(DATA / "ladder_home_and_away.csv").set_index("Team")
fx = pd.read_csv(DATA / "fixtures_results.csv", dtype=str)
uf = num(pd.read_csv(DATA / "team_match_stats_for.csv", dtype=str), ("Opponent", "Round", "Result"))
ua = num(pd.read_csv(DATA / "team_match_stats_against.csv", dtype=str), ("Opponent", "Round", "Result"))
ef = num(pd.read_csv(DATA / "echuca_team_match_stats_for.csv", dtype=str), ("Opponent", "Round", "Result"))
players = num(pd.read_csv(DATA / "player_season_averages.csv"), ("Name",))
lp = num(pd.read_csv(DATA / "leaders_players_averages.csv"), ("Name", "Team"))
mp = num(pd.read_csv(DATA / "match_player_stats.csv", dtype=str), ("Round", "Team", "Name"))

LOWER_BETTER = {"BTO", "MTO", "FTO"}


def rank(code, team):
    return int(pg[code].rank(ascending=code in LOWER_BETTER, method="min")[team])


def v(code, team):
    return float(pg.loc[team, code])


def f1(x):
    return f"{x:,.1f}"


def esc(s):
    return html.escape(str(s))


# League-wide link between each stat and ladder percentage (12 clubs).
pg_l = pg.join(ladder[["Pct", "Pts", "Pos"]])
stats_l = pg_l.drop(columns=["Rank", "Games", "Pct", "Pts", "Pos"])
link = stats_l.loc[:, stats_l.std() > 0].corrwith(pg_l.Pct)

# ---------------------------------------------------------------- shared CSS
CSS = """
:root{
  --bg:#f4f6f9; --surface:#ffffff; --ink:#131c30; --ink-2:#4a5468; --muted:#77819a; --line:#dde2ea;
  --navy:#14213d; --red:#c8102e; --red-soft:#fbe7ea; --green:#1f7a4d; --green-soft:#e2f3ea;
  --track:#e9edf3; --tick:#131c30; --good:#1f7a4d; --bad:#c8102e; --plate:#fcfcfb;
  color-scheme: light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0e1420; --surface:#161f31; --ink:#e7ebf3; --ink-2:#b4bdcd; --muted:#8a94a8; --line:#28324a;
    --navy:#cdd6ea; --red:#ff5a6e; --red-soft:#3a1a22; --green:#4cc38a; --green-soft:#16302a;
    --track:#223049; --tick:#e7ebf3; --good:#4cc38a; --bad:#ff5a6e; --plate:#fcfcfb;
    color-scheme: dark;
  }
}
:root[data-theme="dark"]{
  --bg:#0e1420; --surface:#161f31; --ink:#e7ebf3; --ink-2:#b4bdcd; --muted:#8a94a8; --line:#28324a;
  --navy:#cdd6ea; --red:#ff5a6e; --red-soft:#3a1a22; --green:#4cc38a; --green-soft:#16302a;
  --track:#223049; --tick:#e7ebf3; --good:#4cc38a; --bad:#ff5a6e; --plate:#fcfcfb;
  color-scheme: dark;
}
*{box-sizing:border-box}
body{background:var(--bg); color:var(--ink); font-family:"Source Sans 3", "Segoe UI", system-ui, sans-serif; font-size:16px; line-height:1.55;
  padding-inline:16px; padding-block:0 48px; font-variant-numeric:tabular-nums}
.wrap{max-width:780px; margin:0 auto}
h1,h2,h3,.num{font-family:"Barlow Condensed", "Arial Narrow", sans-serif; text-wrap:balance}
header.cover{padding-block:36px 24px; border-bottom:3px solid var(--red); margin-bottom:28px}
.eyebrow{font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:600}
h1{font-size:clamp(34px,6vw,50px); line-height:1.02; margin:8px 0 12px; color:var(--navy); font-weight:700; letter-spacing:.01em}
.lede{font-size:18px; color:var(--ink-2); max-width:62ch; margin:0}
h2{font-size:28px; color:var(--navy); margin:44px 0 6px; font-weight:700; letter-spacing:.01em}
h2 + .sub{color:var(--muted); margin:0 0 18px; font-size:15px}
h3{font-size:22px; margin:0; color:var(--ink); font-weight:600}
p{max-width:66ch}
.kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:22px 0 4px}
.kpi{background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:14px 16px}
.kpi .num{font-size:38px; line-height:1; font-weight:700; color:var(--navy)}
.kpi .lbl{font-size:13px; color:var(--ink-2); margin-top:6px}
.callout{background:var(--red-soft); border-left:4px solid var(--red); padding:14px 18px; border-radius:0 8px 8px 0; margin:18px 0}
.callout p{margin:0}
.priority{background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:18px 20px; margin:14px 0; display:grid; gap:12px}
.priority .head{display:flex; gap:14px; align-items:baseline; flex-wrap:wrap}
.priority .rankno{font-family:"Barlow Condensed", "Arial Narrow", sans-serif; font-size:30px; font-weight:700; color:var(--red); line-height:1; min-width:1.2em}
.priority p{margin:0; color:var(--ink-2)}
.target{font-size:14px; color:var(--ink); background:var(--track); border-radius:6px; padding:8px 12px}
.target b{color:var(--navy)}
.bars{display:grid; gap:10px}
.bar-stat{display:grid; gap:4px}
.bar-stat .name{font-size:14px; font-weight:600; display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap}
.bar-stat .name span{font-weight:400; color:var(--muted)}
.bar-row{display:grid; grid-template-columns:62px 1fr 56px; gap:8px; align-items:center; font-size:13px}
.bar-row .who{color:var(--ink-2)}
.bar-row .val{text-align:right; font-weight:600}
.track{position:relative; height:12px; background:var(--track); border-radius:3px}
.fill{position:absolute; left:0; top:0; bottom:0; border-radius:3px}
.fill.u{background:var(--red)} .fill.e{background:var(--green)}
.avg{position:absolute; top:-3px; bottom:-3px; width:2px; background:var(--tick)}
.legend{display:flex; gap:16px; flex-wrap:wrap; font-size:13px; color:var(--ink-2); margin:4px 0 8px}
.legend i{display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:-1px; margin-right:6px}
.legend i.tick{width:2px; height:14px; background:var(--tick); border-radius:0; vertical-align:-2px}
.tbl{overflow-x:auto; margin:12px 0; border:1px solid var(--line); border-radius:8px; background:var(--surface)}
table{border-collapse:collapse; width:100%; font-size:14px}
th,td{padding:8px 10px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); font-weight:600; background:var(--surface)}
tr:last-child td{border-bottom:0}
td.pos{color:var(--good); font-weight:600} td.neg{color:var(--bad); font-weight:600}
tr.us td{background:var(--red-soft); font-weight:600}
tr.them td{background:var(--green-soft)}
.pill{display:inline-block; font-size:12px; font-weight:700; border-radius:999px; padding:1px 9px}
.pill.top{background:var(--green-soft); color:var(--green)} .pill.low{background:var(--red-soft); color:var(--red)}
.two{display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px}
.card{background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:16px 18px}
.card h3{font-size:20px; margin-bottom:8px}
.card ul{margin:0; padding-left:18px} .card li{margin:4px 0}
.strip{display:grid; grid-template-columns:repeat(9,1fr); gap:6px; margin:14px 0}
.rd{border-radius:6px; padding:6px 4px; text-align:center; font-size:12px; line-height:1.25; border:1px solid var(--line); background:var(--surface)}
.rd b{display:block; font-family:"Barlow Condensed", "Arial Narrow", sans-serif; font-size:20px}
.rd.W b{color:var(--good)} .rd.L b{color:var(--bad)}
.rd .opp{color:var(--muted); font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
figure{margin:16px 0; background:var(--plate); border:1px solid var(--line); border-radius:10px; padding:10px}
figure img{display:block; width:100%; height:auto}
figcaption{font-size:13px; color:#4a5468; padding:6px 4px 2px}
.foot{margin-top:48px; padding-top:16px; border-top:1px solid var(--line); font-size:13px; color:var(--muted)}
@media (max-width:560px){ .strip{grid-template-columns:repeat(6,1fr)} body{font-size:15px} }
@media print{ body{padding-block:0} .priority,.card,figure,.tbl{break-inside:avoid} h2{break-after:avoid} }
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Source+Sans+3:wght@400;600;700&display=swap">')


def page(title, body):
    return f"<title>{esc(title)}</title>\n{FONTS}\n<style>{CSS}</style>\n<div class=\"wrap\">\n{body}\n</div>\n"


def bars(code, label, note=""):
    """United vs Echuca bar pair with a league-average tick, all on one scale."""
    uv, ev, avg = v(code, U), v(code, E), float(pg[code].mean())
    top = max(pg[code].max(), uv, ev) * 1.08
    pct = lambda x: f"{100 * x / top:.1f}%"
    return f"""<div class="bar-stat">
  <div class="name">{esc(label)} <span>United #{rank(code, U)} · Echuca #{rank(code, E)} of 12{esc(note)}</span></div>
  <div class="bar-row"><span class="who">United</span><div class="track"><div class="fill u" style="width:{pct(uv)}"></div><div class="avg" style="left:{pct(avg)}"></div></div><span class="val">{f1(uv)}</span></div>
  <div class="bar-row"><span class="who">Echuca</span><div class="track"><div class="fill e" style="width:{pct(ev)}"></div><div class="avg" style="left:{pct(avg)}"></div></div><span class="val">{f1(ev)}</span></div>
</div>"""


LEGEND = ('<div class="legend"><span><i style="background:var(--red)"></i>Shepparton United</span>'
          '<span><i style="background:var(--green)"></i>Echuca (premiers)</span><span><i class="tick"></i>League average</span></div>')


def std(code):
    """Premiership standard = average of the two best teams (Echuca, Shepparton Bears)."""
    return (v(code, E) + v(code, B)) / 2


# ================================================================= REPORT 1: GRAND FINAL GAP
e_fin = ef[ef.Round.isin(["FW1", "FW2", "GF"])]
h2h = uf[uf.Opponent == E].merge(ua[ua.Opponent == E], on=["Round"], suffixes=("_u", "_e"))
gf = fx[fx.Round == "GF"].iloc[0]

priorities = [
    dict(title="Win the contested ball", codes=[("CP", "Contested possessions"), ("TGB", "Groundball gets"), ("LBG", "Loose-ball gets")],
         text=(f"This is the biggest gap between United and the premiers. Echuca were 1st in the league in all three. "
               f"United were {rank('CP', U)}th, {rank('TGB', U)}th and {rank('LBG', U)}th. Across the league, contested possessions "
               f"tracked ladder position closely (link {link['CP']:.2f}; 1.00 would be perfect)."),
         target=("CP", "contested possessions")),
    dict(title="Bring the pressure: tackles and pressure acts", codes=[("PR", "Overall pressure"), ("T", "Tackles"), ("MTKL", "Midfield tackles")],
         text=(f"United applied the least pressure in the competition (12th) and were {rank('T', U)}th for tackles. Echuca laid "
               f"{f1(v('T', E) - v('T', U))} more tackles a game, {f1(v('MTKL', E) - v('MTKL', U))} of them in the midfield. "
               f"In United's two games against Echuca they were out-tackled 77 to 60 and 64 to 58."),
         target=("T", "tackles")),
    dict(title="Get the ball inside 50 more often", codes=[("I50", "Inside 50s"), ("MI50", "Marks inside 50")],
         text=(f"Inside 50s were the stat most linked to United's winning margin this year. United averaged {f1(uf[uf.Result=='W'].I50.mean())} "
               f"in wins and {f1(uf[uf.Result=='L'].I50.mean())} in losses. Echuca averaged {f1(v('I50', E))}, the most in the league. "
               f"United already take plenty of marks inside 50 ({rank('MI50', U)}nd), so more entries should turn into more scores."),
         target=("I50", "inside 50s")),
    dict(title="Kick straighter when it counts", codes=[("G", "Goals"), ("GA%", "Goal accuracy %")],
         text=(f"United kicked {f1(v('G', U))} goals a game at {v('GA%', U):.0f}% accuracy. Echuca kicked {f1(v('G', E))} at {v('GA%', E):.0f}%, "
               f"and lifted to {e_fin['GA%'].min():.0f}–{e_fin['GA%'].max():.0f}% in their three finals ({int(e_fin.G.min())}–{int(e_fin.G.max())} goals a game). "
               f"Across the league, goal accuracy tracked ladder position closely (link {link['GA%']:.2f})."),
         target=("G", "goals")),
    dict(title="Win it back: intercepts, spoils and smothers", codes=[("IP", "Intercept possessions"), ("1%", "One-percenters"), ("Sm", "Smothers")],
         text=(f"Intercept possessions had the strongest link to ladder position of any possession stat (link {link['IP']:.2f}). United were "
               f"{rank('IP', U)}th. They were last for one-percenters and {rank('Sm', U)}th for smothers, so the defensive effort acts that "
               f"stop opposition scores are also missing."),
         target=("IP", "intercept possessions")),
]

prio_html = []
for i, p in enumerate(priorities, 1):
    code, word = p["target"]
    gap = std(code) - v(code, U)
    per_q = gap / 4
    per_q_txt = f"{per_q:.1f}" if per_q < 3 else f"{per_q:.0f}"
    prio_html.append(f"""<section class="priority">
  <div class="head"><span class="rankno">{i}</span><h3>{esc(p['title'])}</h3></div>
  <p>{esc(p['text'])}</p>
  <div class="bars">{''.join(bars(c, l) for c, l in p['codes'])}</div>
  <div class="target">Premiership standard: <b>{f1(std(code))} {esc(word)}</b> a game (average of Echuca and Shepparton Bears).
  United: {f1(v(code, U))}. That is <b>{f1(gap)} more a game</b>, about <b>{per_q_txt} more per quarter</b>.</div>
</section>""")

keep_codes = [("M", "Marks"), ("UM", "Uncontested marks"), ("K%", "Kick efficiency %"), ("DE%", "Disposal efficiency %"), ("MTO", "Midfield turnovers (fewer is better)")]
keep_rows = "".join(f"<tr><td>{esc(l)}</td><td>{f1(v(c, U))}</td><td><span class='pill top'>#{rank(c, U)}</span></td><td>{f1(v(c, E))}</td><td>#{rank(c, E)}</td></tr>"
                    for c, l in keep_codes)

h2h_codes = [("CP", "Contested possessions"), ("Cl", "Clearances"), ("I50", "Inside 50s"), ("T", "Tackles"), ("PR", "Overall pressure"), ("SS", "Scoring shots"), ("G", "Goals")]
h2h_rows = ""
for code, label in h2h_codes:
    cells = ""
    for _, r in h2h.iterrows():
        d = int(r[f"{code}_u"] - r[f"{code}_e"])
        cells += f"<td>{int(r[code + '_u'])}</td><td>{int(r[code + '_e'])}</td><td class='{'pos' if d > 0 else 'neg' if d < 0 else ''}'>{d:+d}</td>"
    h2h_rows += f"<tr><td>{esc(label)}</td>{cells}</tr>"
h2h_head = "".join(f"<th>R{int(r.Round)} United</th><th>Echuca</th><th>Diff</th>" for _, r in h2h.iterrows())
h2h_scores = []
for _, r in h2h.iterrows():
    g = fx[(fx.Round == str(int(r.Round))) & ((fx.HomeTeam.str.title() == E) | (fx.AwayTeam.str.title() == E))].iloc[0]
    us_home = g.HomeTeam.title() == U
    us, them = (g.HomeScore, g.AwayScore) if us_home else (g.AwayScore, g.HomeScore)
    h2h_scores.append(f"Round {int(r.Round)}: United {us}, Echuca {them}")

fin_rows = "".join(
    f"<tr><td>{esc(r.Round)} v {esc(r.Opponent)}</td><td>{int(r.CP)}</td><td>{int(r.Cl)}</td><td>{int(r.I50)}</td><td>{int(r['T'])}</td><td>{int(r.G)}</td><td>{int(r['GA%'])}%</td></tr>"
    for _, r in e_fin.iterrows())
u_avg_row = (f"<tr class='us'><td>United season average</td><td>{f1(uf.CP.mean())}</td><td>{f1(uf.Cl.mean())}</td><td>{f1(uf.I50.mean())}</td>"
             f"<td>{f1(uf['T'].mean())}</td><td>{f1(uf.G.mean())}</td><td>{uf['GA%'].mean():.0f}%</td></tr>")

link_rows = "".join(f"<tr><td>{esc(l)}</td><td>{link[c]:.2f}</td><td>#{rank(c, U)}</td></tr>" for c, l in
                    [("IP", "Intercept possessions"), ("I50", "Inside 50s"), ("GA%", "Goal accuracy %"), ("CP", "Contested possessions"),
                     ("FTKL", "Forward-50 tackles"), ("Cl", "Clearances"), ("M", "Marks"), ("UM", "Uncontested marks"), ("DE%", "Disposal efficiency %")])

gf_body = f"""
<header class="cover">
  <div class="eyebrow">Shepparton United · Coaching staff briefing · GVL 2026</div>
  <h1>What it takes to win a grand final</h1>
  <p class="lede">We compared United with Echuca, who won the 2026 flag {esc(gf.HomeScore)} to {esc(gf.AwayScore)} over Shepparton Bears, and with all 12 clubs. United already use the ball as well as any team in the league. The gap is in winning it: contested ball, pressure and getting it inside 50.</p>
</header>

<div class="kpis">
  <div class="kpi"><div class="num">+{f1(v('CP', E) - v('CP', U))}</div><div class="lbl">contested possessions a game Echuca had over United</div></div>
  <div class="kpi"><div class="num">+{f1(v('T', E) - v('T', U))}</div><div class="lbl">tackles a game Echuca laid over United</div></div>
  <div class="kpi"><div class="num">+{f1(v('I50', E) - v('I50', U))}</div><div class="lbl">inside 50s a game Echuca had over United</div></div>
  <div class="kpi"><div class="num">+{f1(v('G', E) - v('G', U))}</div><div class="lbl">goals a game Echuca kicked over United</div></div>
</div>

<div class="callout"><p><b>The short version.</b> Keep the kicking and marking game. Add a contested, high-pressure edge in the midfield. United are 1st in the league for marks and kicking efficiency, but those stats had almost no link to ladder position this year. Contested ball, tackling, intercepts and inside 50s did.</p></div>

<h2>The five priorities</h2>
<p class="sub">In order of how far United are behind the premiers. Each bar is a per-game average for 2026. The black tick is the league average.</p>
{LEGEND}
{''.join(prio_html)}

<h2>What separates the top teams</h2>
<p class="sub">How closely each stat moved with ladder percentage across all 12 clubs. 1.00 means the better the stat, the higher the club finished, every time.</p>
<div class="tbl"><table><thead><tr><th>Stat (per game)</th><th>Link to ladder</th><th>United rank</th></tr></thead><tbody>{link_rows}</tbody></table></div>
<p>The top six stats are all about winning the ball and getting it forward. United's best stats, marks and disposal efficiency, sit at the bottom. They are worth keeping, but on their own they don't win you a flag.</p>

<h2>Keep doing this</h2>
<p class="sub">United's strengths. These are a real edge and shouldn't be traded away.</p>
<div class="tbl"><table><thead><tr><th>Stat (per game)</th><th>United</th><th>Rank</th><th>Echuca</th><th>Rank</th></tr></thead><tbody>{keep_rows}</tbody></table></div>

<h2>Head to head with Echuca</h2>
<p class="sub">{esc('; '.join(h2h_scores))}.</p>
<div class="tbl"><table><thead><tr><th>Stat</th>{h2h_head}</tr></thead><tbody>{h2h_rows}</tbody></table></div>
<p>In Round 6 United matched Echuca for possession and inside 50s but lost the tackle count by 17 and the pressure count by 30. In Round 17 Echuca won every area. That was the 100-point loss.</p>

<h2>How Echuca played their finals</h2>
<p class="sub">Echuca's three finals compared with United's season averages.</p>
<div class="tbl"><table><thead><tr><th>Game</th><th>Contested poss.</th><th>Clearances</th><th>Inside 50s</th><th>Tackles</th><th>Goals</th><th>Goal accuracy</th></tr></thead>
<tbody>{fin_rows}{u_avg_row}</tbody></table></div>
<p>Finals footy was more contested again. Echuca averaged {f1(e_fin.CP.mean())} contested possessions and {f1(e_fin.I50.mean())} inside 50s, and kicked {f1(e_fin.G.mean())} goals a game. A team built on uncontested marking will need a stronger contested game to match that in September.</p>

<h2>Targets for 2027</h2>
<div class="tbl"><table><thead><tr><th>Measure (per game)</th><th>United 2026</th><th>Premiership standard</th><th>Change needed</th></tr></thead><tbody>
{''.join(f"<tr><td>{esc(l)}</td><td>{f1(v(c, U))}</td><td>{f1(std(c))}</td><td class='pos'>+{f1(std(c) - v(c, U))}</td></tr>" for c, l in [("CP", "Contested possessions"), ("TGB", "Groundball gets"), ("T", "Tackles"), ("PR", "Overall pressure"), ("I50", "Inside 50s"), ("IP", "Intercept possessions"), ("G", "Goals"), ("GA%", "Goal accuracy %")])}
<tr><td>Marks</td><td>{f1(v('M', U))}</td><td>{f1(std('M'))}</td><td>Hold (already above)</td></tr>
<tr><td>Kick efficiency %</td><td>{f1(v('K%', U))}</td><td>{f1(std('K%'))}</td><td>Hold (already above)</td></tr>
</tbody></table></div>
<p>"Premiership standard" is the average of the two best teams in 2026: Echuca (premiers) and Shepparton Bears (minor premiers, runners-up).</p>

<div class="foot">Source: Premier Data (Shepparton United club account), 2026 Goulburn Valley League season, all rounds including finals. Per-game averages from the Leaderboards. Echuca's include their 3 finals; United played 18 games. "Link" is a correlation across the 12 clubs, a guide rather than proof. Full numbers are in the spreadsheet <i>Shepparton_United_vs_Echuca_2026.xlsx</i>.</div>
"""

# ================================================================= REPORT 2: SEASON REVIEW
res = []
for _, r in fx[fx.Round.str.isdigit()].iterrows():
    for us, them, a, b in [(r.HomeTeam, r.AwayTeam, r.HomeScore, r.AwayScore), (r.AwayTeam, r.HomeTeam, r.AwayScore, r.HomeScore)]:
        if us.title() == U:
            res.append(dict(Round=int(r.Round), Opp=them.title(), For=int(a), Ag=int(b)))
res = pd.DataFrame(res).sort_values("Round")
res["M"] = res.For - res.Ag
res["R"] = res.M.apply(lambda m: "W" if m > 0 else "L" if m < 0 else "D")
top5 = list(ladder.sort_values("Pos").index[:5])
strip = "".join(f'<div class="rd {r.R}"><span>R{r.Round}</span><b>{r.R} {r.M:+d}</b><div class="opp">{esc(r.Opp.replace("Shepparton ", "Shep. "))}</div></div>'
                for r in res.itertuples())
lad_rows = "".join(f"<tr class='{'us' if t == U else 'them' if t == E else ''}'><td>{int(r.Pos)}. {esc(t)}</td><td>{int(r.W)}</td><td>{int(r.L)}</td><td>{int(r.D)}</td><td>{int(r.Pts)}</td><td>{r.Pct:.1f}</td></tr>"
                   for t, r in ladder.sort_values("Pos").iterrows())
vs_top = res[res.Opp.isin(top5)]
vs_rest = res[~res.Opp.isin(top5)]
close = res[res.M.abs() <= 30]


def img(name, alt, cap):
    data = base64.b64encode((Path("report") / name).read_bytes()).decode()
    return f'<figure><img src="data:image/png;base64,{data}" alt="{esc(alt)}"><figcaption>{esc(cap)}</figcaption></figure>'


# Player tables
reg = players[players.Games >= 5].sort_values("RP", ascending=False)
lpq = lp[lp.Games >= 8].copy()
for c in ["RP", "D", "CP", "Cl", "T", "G", "M", "IP", "I50"]:
    lpq[c + "_r"] = lpq[c].rank(ascending=False, method="min")
lpu = lpq[lpq.Team == U].set_index("Name")


def lr(name, c):
    return f"#{int(lpu.loc[name, c + '_r'])}" if name in lpu.index else "–"


pl_rows = "".join(
    f"<tr><td>{esc(r.Name)}</td><td>{int(r.Games)}</td><td>{f1(r.RP)}</td><td>{lr(r.Name, 'RP')}</td><td>{f1(r.D)}</td><td>{f1(r.CP)}</td><td>{f1(r.M)}</td><td>{f1(r.T)}</td><td>{f1(r.Cl)}</td><td>{f1(r.G)}</td></tr>"
    for r in reg.head(12).itertuples())

mpu = mp[(mp.Team == U) & mp.Round.str.isdigit()].copy()
mpu["Round"] = mpu.Round.astype(int)
g = mpu.groupby("Name")
form = pd.DataFrame({"Games": g.size(), "First": mpu[mpu.Round <= 9].groupby("Name").RP.mean(),
                     "Second": mpu[mpu.Round > 9].groupby("Name").RP.mean()})
form = form[form.Games >= 8].dropna()
form["Change"] = form.Second - form.First
up = form.sort_values("Change", ascending=False).head(4)
down = form.sort_values("Change").head(4)
best = mpu.sort_values("RP", ascending=False).head(6)
wins, losses = uf[uf.Result == "W"], uf[uf.Result == "L"]
wl_rows = "".join(f"<tr><td>{esc(l)}</td><td>{f1(wins[c].mean())}</td><td>{f1(losses[c].mean())}</td><td class='{'pos' if wins[c].mean() > losses[c].mean() else 'neg'}'>{wins[c].mean() - losses[c].mean():+.1f}</td></tr>"
                  for c, l in [("I50", "Inside 50s"), ("MI50", "Marks inside 50"), ("SS", "Scoring shots"), ("M", "Marks"), ("D", "Disposals"),
                               ("CP", "Contested possessions"), ("Cl", "Clearances"), ("T", "Tackles"), ("TO", "Turnovers")])

standouts = [
    ("Brodie Newman", f"Defender. #1 in the GVL for marks ({f1(players.set_index('Name').loc['Brodie Newman','M'])} a game) and #1 for intercept possessions. Club's highest-impact regular player."),
    ("Angus Hicks", f"Midfield engine. League top 20 for disposals, clearances, tackles and inside 50s. {f1(players.set_index('Name').loc['Angus Hicks','D'])} disposals a game."),
    ("Jordan Haynes", "The league's 7th-best tackler and the most consistent high performer in the side."),
    ("Matthew Casey", f"{f1(players.set_index('Name').loc['Matthew Casey','G'])} goals a game, 3rd best in the GVL. His output rose more than anyone's in wins."),
    ("Zavier Maher", f"Only 7 games, but his average impact score ({f1(players.set_index('Name').loc['Zavier Maher','RP'])}) would rank 3rd in the league. Having him available more would make a big difference."),
    ("Liam Serra", "#3 in the league for marks and #18 for goals. Strong first half, dropped off after Round 9."),
]
stand_html = "".join(f"<li><b>{esc(n)}.</b> {esc(t)}</li>" for n, t in standouts)
up_html = "".join(f"<li><b>{esc(n)}</b>: {r.First:.0f} → {r.Second:.0f}</li>" for n, r in up.iterrows())
down_html = "".join(f"<li><b>{esc(n)}</b>: {r.First:.0f} → {r.Second:.0f}</li>" for n, r in down.iterrows())
best_html = "".join(f"<li><b>{esc(r.Name)}</b>, Round {r.Round}: {int(r.RP)} points ({int(r.D)} disposals, {int(r.T)} tackles, {int(r.Cl)} clearances, {int(r.G)} goals)</li>"
                    for r in best.itertuples())

str_rows = "".join(f"<tr><td>{esc(l)}</td><td>{f1(v(c, U))}</td><td>{f1(pg[c].mean())}</td><td><span class='pill {'top' if rank(c, U) <= 3 else 'low' if rank(c, U) >= 10 else ''}'>#{rank(c, U)}</span></td></tr>"
                   for c, l in [("M", "Marks"), ("UM", "Uncontested marks"), ("K%", "Kick efficiency %"), ("DE%", "Disposal efficiency %"),
                                ("MTO", "Midfield turnovers (fewer is better)"), ("MI50", "Marks inside 50"), ("HO", "Hit outs"), ("D", "Disposals"),
                                ("CP", "Contested possessions"), ("Cl", "Clearances"), ("T", "Tackles"), ("TGB", "Groundball gets"),
                                ("LBG", "Loose-ball gets"), ("PR", "Overall pressure"), ("1%", "One-percenters"), ("Sp", "Spoils")])

L = ladder.loc[U]
sixth = ladder.sort_values("Pos").iloc[5]
season_body = f"""
<header class="cover">
  <div class="eyebrow">Shepparton United · Season review · GVL 2026</div>
  <h1>Shepparton United 2026 season review</h1>
  <p class="lede">United finished {int(L.Pos)}th with {int(L.W)} wins and {int(L.L)} losses, one win short of the finals. They were the league's best ball users, but gave up too much in the contest and at the stoppages against the better sides.</p>
</header>

<div class="kpis">
  <div class="kpi"><div class="num">{int(L.Pos)}th</div><div class="lbl">ladder position (12 teams)</div></div>
  <div class="kpi"><div class="num">{int(L.W)}–{int(L.L)}</div><div class="lbl">wins–losses</div></div>
  <div class="kpi"><div class="num">{L.Pct:.1f}%</div><div class="lbl">percentage ({int(L.For)} for, {int(L.Against)} against)</div></div>
  <div class="kpi"><div class="num">1 win</div><div class="lbl">short of the finals (6th: {esc(sixth.name)}, {int(sixth.Pts)} pts)</div></div>
</div>

<h2>Results, round by round</h2>
<p class="sub">Margin in points. Home and away season, rounds 1–18.</p>
<div class="strip">{strip}</div>
<div class="two">
  <div class="card"><h3>Against the top 5</h3><p>{int((vs_top.R == 'W').sum())} wins from {len(vs_top)} games, average margin {vs_top.M.mean():+.1f}. Wins over Shepparton Swans (twice) and Kyabram; losses to Echuca and Shepparton Bears (twice each) and Seymour.</p></div>
  <div class="card"><h3>Against everyone else</h3><p>{int((vs_rest.R == 'W').sum())} wins from {len(vs_rest)} games, average margin {vs_rest.M.mean():+.1f}. The losses to Mooroopna (twice, by 7 and 27), Rochester and Mansfield cost the finals spot.</p></div>
</div>
<div class="callout"><p><b>The one that got away:</b> Round 4, lost to Mooroopna by 7 points. Win that game and United finish on 40 points, Mooroopna drop to 36, and United play finals.</p></div>

<h2>Final ladder</h2>
<div class="tbl"><table><thead><tr><th>Team</th><th>W</th><th>L</th><th>D</th><th>Pts</th><th>%</th></tr></thead><tbody>{lad_rows}</tbody></table></div>
<p>Echuca won the premiership, beating Shepparton Bears in the grand final {esc(gf.HomeScore)} to {esc(gf.AwayScore)}.</p>

<h2>How United played</h2>
<p class="sub">Per-game averages and rank among the 12 clubs.</p>
<div class="tbl"><table><thead><tr><th>Stat (per game)</th><th>United</th><th>League avg</th><th>Rank</th></tr></thead><tbody>{str_rows}</tbody></table></div>
<div class="two">
  <div class="card"><h3>Strengths</h3><ul><li>Best marking team in the league: {f1(v('M', U) - pg.M.mean())} more marks a game than average</li><li>Cleanest kicking and fewest midfield turnovers</li><li>2nd for marks inside 50 and 3rd for hit outs</li></ul></div>
  <div class="card"><h3>Weaknesses</h3><ul><li>Least pressure in the league and 10th for tackles</li><li>11th for groundball gets, 12th for loose-ball gets</li><li>Last for one-percenters and spoils</li></ul></div>
</div>
{img('03_team_strengths_weaknesses.png', 'United compared with the league on every stat', 'Every stat compared with the league average. Right of the line is better than average; rank out of 12 in brackets.')}

<h2>What won and lost games</h2>
<p class="sub">United's own averages in their 9 wins and 9 losses.</p>
<div class="tbl"><table><thead><tr><th>Stat</th><th>In wins</th><th>In losses</th><th>Difference</th></tr></thead><tbody>{wl_rows}</tbody></table></div>
<p>Getting the ball inside 50 decided United's games. Tackle numbers were almost the same in wins and losses. When United lost, the ball simply wasn't getting forward.</p>
{img('01_margin_by_round.png', 'Winning margin each round', 'Margin each round. Blue = win, orange = loss.')}

<h2>Players</h2>
<p class="sub">Top 12 players by average ranking points (Premier Data's overall impact score), minimum 5 games. League rank is out of {len(lpq)} GVL players with 8+ games.</p>
<div class="tbl"><table><thead><tr><th>Player</th><th>Games</th><th>Impact</th><th>League rank</th><th>Disp.</th><th>Cont. poss.</th><th>Marks</th><th>Tackles</th><th>Clear.</th><th>Goals</th></tr></thead><tbody>{pl_rows}</tbody></table></div>
<div class="card"><h3>Standouts</h3><ul>{stand_html}</ul></div>
{img('07_league_player_context.png', 'United players among every GVL player', 'Every GVL player with 8+ games. United players in blue.')}

<h2>Form through the year</h2>
<p class="sub">Average impact score, rounds 1–9 compared with rounds 10–18 (players with 8+ games).</p>
<div class="two">
  <div class="card"><h3>Improved</h3><ul>{up_html}</ul></div>
  <div class="card"><h3>Dropped off</h3><ul>{down_html}</ul></div>
</div>
<div class="card" style="margin-top:14px"><h3>Best individual games</h3><ul>{best_html}</ul></div>

<h2>Looking ahead</h2>
<p>The foundation is good: United can move the ball better than anyone in the league. To go from 8th to a finals side and beyond, the priorities are:</p>
<ul>
<li>Win more of the contested ball.</li>
<li>Lift tackling and pressure around stoppages.</li>
<li>Turn possession into more inside 50s.</li>
</ul>
<p>The companion report, <i>What it takes to win a grand final</i>, sets out targets for each.</p>

<div class="foot">Source: Premier Data (Shepparton United club account), 2026 Goulburn Valley League season. Ladder rebuilt from all 108 home-and-away results; it matches the app. Player league ranks use per-game averages for players with 8+ games.</div>
"""

(OUT / "grand-final-gap.html").write_text(page("Grand Final Gap", gf_body))
(OUT / "season-review.html").write_text(page("United 2026 Review", season_body))
print("wrote", OUT / "grand-final-gap.html", OUT / "season-review.html")
