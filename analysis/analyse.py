"""Analyse the scraped Premier Data CSVs (data/) and write charts to report/ plus a findings JSON.

Run from the repo root:  python3 analysis/analyse.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA = Path("data")
OUT = Path("report")
OUT.mkdir(exist_ok=True)
TEAM = "Shepparton United"

# Reference palette (validated): blue = our team / positive, orange = negative, grey = context.
BLUE, ORANGE, GREY, INK, INK2, GRID, SURF = "#2a78d6", "#eb6834", "#c3c2b7", "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "font.size": 10, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def num(df, skip=()):
    for c in df.columns:
        if c not in skip:
            conv = pd.to_numeric(df[c].astype(str).str.replace(",", "").str.rstrip("%"), errors="coerce")
            if conv.notna().any():
                df[c] = conv
    return df


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)


findings = {}

# ---------------------------------------------------------------- results & ladder
fx = pd.read_csv(DATA / "fixtures_results.csv", dtype=str)
fx["HomeTeam"] = fx.HomeTeam.str.title()
fx["AwayTeam"] = fx.AwayTeam.str.title()
fx[["HomeScore", "AwayScore"]] = fx[["HomeScore", "AwayScore"]].astype(int)
games = []
for _, r in fx.iterrows():
    for us, them, f, a, venue in [(r.HomeTeam, r.AwayTeam, r.HomeScore, r.AwayScore, "Home"),
                                  (r.AwayTeam, r.HomeTeam, r.AwayScore, r.HomeScore, "Away")]:
        games.append(dict(Round=r.Round, Team=us, Opponent=them, For=f, Against=a, Margin=f - a, Venue=venue,
                          Result="W" if f > a else "L" if f < a else "D"))
games = pd.DataFrame(games)
ha = games[games.Round.str.isdigit()].copy()
ha["Round"] = ha.Round.astype(int)
ladder = ha.groupby("Team").agg(P=("Result", "size"), W=("Result", lambda s: (s == "W").sum()),
                                L=("Result", lambda s: (s == "L").sum()), D=("Result", lambda s: (s == "D").sum()),
                                For=("For", "sum"), Against=("Against", "sum"))
ladder["Pts"] = ladder.W * 4 + ladder.D * 2
ladder["Pct"] = (100 * ladder.For / ladder.Against).round(1)
ladder = ladder.sort_values(["Pts", "Pct"], ascending=False)
ladder.insert(0, "Pos", range(1, len(ladder) + 1))
ladder.to_csv(DATA / "ladder_home_and_away.csv")

us = ha[ha.Team == TEAM].sort_values("Round")
findings["ladder"] = dict(pos=int(ladder.loc[TEAM, "Pos"]), W=int(ladder.loc[TEAM, "W"]), L=int(ladder.loc[TEAM, "L"]),
                          pct=float(ladder.loc[TEAM, "Pct"]), pts=int(ladder.loc[TEAM, "Pts"]),
                          finals_teams=sorted(set(games[~games.Round.str.isdigit()].Team)),
                          premier=fx[fx.Round == "GF"].apply(lambda r: r.HomeTeam if r.HomeScore > r.AwayScore else r.AwayTeam, axis=1).tolist())
findings["results"] = us[["Round", "Opponent", "Venue", "For", "Against", "Margin", "Result"]].to_dict("records")
first, second = us[us.Round <= 9], us[us.Round > 9]
findings["halves"] = dict(first_W=int((first.Result == "W").sum()), second_W=int((second.Result == "W").sum()),
                          first_margin=round(first.Margin.mean(), 1), second_margin=round(second.Margin.mean(), 1))
vs_top = us[us.Opponent.isin(ladder.index[:5])]
vs_rest = us[~us.Opponent.isin(ladder.index[:5])]
findings["vs_top5"] = dict(W=int((vs_top.Result == "W").sum()), G=len(vs_top), avg_margin=round(vs_top.Margin.mean(), 1))
findings["vs_rest"] = dict(W=int((vs_rest.Result == "W").sum()), G=len(vs_rest), avg_margin=round(vs_rest.Margin.mean(), 1))

fig, ax = plt.subplots(figsize=(10, 4.2))
colors = [BLUE if m > 0 else ORANGE for m in us.Margin]
ax.bar(us.Round, us.Margin, color=colors, width=0.7, edgecolor=SURF, linewidth=2)
ax.axhline(0, color=INK2, linewidth=1)
for rd, m, opp in zip(us.Round, us.Margin, us.Opponent):
    ax.annotate(opp.replace("Shepparton ", "Shep. "), (rd, m), xytext=(0, 4 if m > 0 else -4), textcoords="offset points",
                ha="center", va="bottom" if m > 0 else "top", fontsize=7, color=INK2, rotation=90)
ax.set_xticks(us.Round)
ax.set_xlabel("Round")
ax.set_ylabel("Winning margin (points)")
ax.set_title(f"{TEAM}: result margin each round (blue = win, orange = loss)")
ax.set_ylim(us.Margin.min() - 45, us.Margin.max() + 45)
save(fig, "01_margin_by_round.png")

# ladder chart: percentage vs points
fig, ax = plt.subplots(figsize=(10, 4.5))
lad = ladder.reset_index()
ax.barh(lad.Team[::-1], lad.Pts[::-1], color=[BLUE if t == TEAM else GREY for t in lad.Team[::-1]], height=0.7, edgecolor=SURF, linewidth=2)
for i, (t, p, pct) in enumerate(zip(lad.Team[::-1], lad.Pts[::-1], lad.Pct[::-1])):
    ax.text(p + 0.8, i, f"{p} pts  ({pct:.0f}%)", va="center", fontsize=8, color=INK2)
ax.set_xlabel("Premiership points (home & away, rounds 1-18)")
ax.set_title("GVL 2026 home & away ladder (percentage in brackets)")
ax.grid(axis="y", visible=False)
ax.set_xlim(0, lad.Pts.max() + 14)
save(fig, "02_ladder.png")

# ---------------------------------------------------------------- team strengths vs league
ta = num(pd.read_csv(DATA / "leaders_teams_averages.csv"), skip=("Name",)).set_index("Name")
# Stats where a HIGHER number is BAD for the team.
bad = {"FA", "GST", "BTO", "MTO", "FTO", "KO"}
labels = {"RP": "Ranking points", "D": "Disposals", "K": "Kicks", "HB": "Handballs", "CP": "Contested possessions",
          "M": "Marks", "Cl": "Clearances", "I50": "Inside 50s", "G": "Goals", "SI": "Score involvements",
          "IP": "Intercept possessions", "T": "Tackles", "HO": "Hit outs", "HOA": "Hit outs to advantage",
          "TGB": "Groundball gets", "CM": "Contested marks", "UM": "Uncontested marks", "IM": "Intercept marks",
          "MI50": "Marks inside 50", "CC": "Centre clearances", "R50": "Rebound 50s", "FF": "Frees for",
          "FA": "Frees against", "1%": "One-percenters", "BTO": "Back-half turnovers", "MTO": "Midfield turnovers",
          "FTO": "Forward-half turnovers", "PR": "Overall pressure", "PRA": "Pressure acts", "Ch": "Chases", "Sm": "Smothers", "Sp": "Spoils",
          "GA%": "Goal accuracy %", "DE%": "Disposal efficiency %", "K%": "Kick efficiency %", "H%": "Handball efficiency %",
          "I50%": "Inside-50 efficiency %", "C%": "Clearance %", "R50%": "Rebound-50 efficiency %", "BUC": "Ball-up clearances",
          "LBG": "Loose-ball gets", "HBG": "Hard-ball gets", "GA": "Goal assists", "B": "Behinds"}
# Skip stats with no spread across teams (e.g. frees against is recorded as 0 for everyone) and
# rebound 50s, which has no clear good/bad direction (few can simply mean little time defending).
cols = [c for c in labels if c in ta.columns and ta[c].std() > 0 and c != "R50"]
z = (ta[cols] - ta[cols].mean()) / ta[cols].std(ddof=0)
for c in cols:
    if c in bad:
        z[c] = -z[c]
rank = ta[cols].rank(ascending=False, method="min")
for c in cols:
    if c in bad:
        rank[c] = ta[c].rank(ascending=True, method="min")
uz = z.loc[TEAM].drop(["B"], errors="ignore").sort_values()
findings["team_rank"] = {labels[c]: dict(value=float(ta.loc[TEAM, c]), rank=int(rank.loc[TEAM, c]), league_avg=round(float(ta[c].mean()), 1))
                         for c in cols}
findings["strengths"] = [labels[c] for c in uz.index[::-1][:8]]
findings["weaknesses"] = [labels[c] for c in uz.index[:8]]

fig, ax = plt.subplots(figsize=(10, 9))
ax.barh([f"{labels[c]}  (#{int(rank.loc[TEAM, c])})" for c in uz.index], uz.values,
        color=[BLUE if v > 0 else ORANGE for v in uz.values], height=0.72, edgecolor=SURF, linewidth=2)
ax.axvline(0, color=INK2, linewidth=1)
ax.set_xlabel("Standard deviations from the league average (right = better than average)")
ax.set_title(f"{TEAM} vs the other 11 GVL clubs (per-game averages)\nRank of 12 in brackets; right is better (turnovers flipped)")
ax.grid(axis="y", visible=False)
save(fig, "03_team_strengths_weaknesses.png")

# season for vs against differential
sfa = pd.read_csv(DATA / "team_season_for_vs_against.csv").drop_duplicates("Stat Type")
sfa = num(sfa, skip=("Stat Type",))
findings["for_against"] = sfa.set_index("Stat Type")[["For", "Against", "Differential"]].to_dict("index")

# ---------------------------------------------------------------- round-by-round trends
tf = num(pd.read_csv(DATA / "team_match_stats_for.csv", dtype=str), skip=("Opponent", "Result"))
tg = num(pd.read_csv(DATA / "team_match_stats_against.csv", dtype=str), skip=("Opponent", "Result"))
td = num(pd.read_csv(DATA / "team_match_stats_differential.csv", dtype=str), skip=("Opponent", "Result"))
td = td.merge(us[["Round", "Margin"]], on="Round", how="left")
corr_cols = [c for c in ["D", "K", "HB", "CP", "TGB", "M", "CM", "UM", "IM", "MI50", "Cl", "CC", "I50", "R50", "T", "PR", "TO", "HO", "IP", "RP", "FF", "SS"]
             if c in td.columns]
corr = td[corr_cols].corrwith(td.Margin).sort_values(ascending=False)
nice = dict(labels, TO="Turnovers", SS="Scoring shots")
findings["margin_drivers"] = {nice.get(c, c): round(v, 2) for c, v in corr.items()}
wins, losses = tf[tf.Result == "W"], tf[tf.Result == "L"]
findings["win_vs_loss_for"] = {nice.get(c, c): (round(wins[c].mean(), 1), round(losses[c].mean(), 1)) for c in corr_cols if c in tf.columns}

fig, ax = plt.subplots(figsize=(10, 5))
top = corr.head(6).index.tolist() + corr.tail(3).index.tolist()
vals = corr[top][::-1]
ax.barh([nice.get(c, c) for c in vals.index], vals.values, color=[BLUE if v > 0 else ORANGE for v in vals.values], height=0.7,
        edgecolor=SURF, linewidth=2)
ax.axvline(0, color=INK2, linewidth=1)
ax.set_xlim(-1, 1)
ax.set_xlabel("Correlation between winning that stat and the final margin (1 = moves perfectly together)")
ax.set_title(f"What decided {TEAM}'s games\nHow closely beating the opponent on each stat tracked the final margin")
ax.grid(axis="y", visible=False)
save(fig, "04_what_wins_games.png")

fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
for ax, (c, name) in zip(axes.flat, [("CP", "Contested possessions"), ("I50", "Inside 50s"), ("T", "Tackles"), ("Cl", "Clearances")]):
    ax.plot(tf.Round, tf[c], color=BLUE, linewidth=2, marker="o", markersize=5, label=TEAM)
    ax.plot(tg.Round, tg[c], color=ORANGE, linewidth=2, marker="o", markersize=5, label="Opponent")
    for rd, v, res in zip(tf.Round, tf[c], tf.Result):
        ax.annotate(res, (rd, v), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=7, color=INK2)
    ax.set_title(name, fontsize=11)
axes[0, 0].legend(frameon=False, fontsize=9)
for ax in axes[1]:
    ax.set_xlabel("Round")
    ax.set_xticks(range(1, 19))
fig.suptitle(f"Round-by-round: {TEAM} (blue) vs opponent (orange); W/L marked", x=0.01, ha="left", fontweight="bold")
save(fig, "05_trends_key_stats.png")

# ---------------------------------------------------------------- players
pa = num(pd.read_csv(DATA / "player_season_averages.csv"), skip=("Name",))
reg = pa[pa.Games >= 5].copy()
findings["squad_size"] = len(pa)
top_players = {}
for c, name in [("RP", "Ranking points"), ("D", "Disposals"), ("CP", "Contested possessions"), ("Cl", "Clearances"),
                ("T", "Tackles"), ("G", "Goals"), ("M", "Marks"), ("I50", "Inside 50s"), ("R50", "Rebound 50s")]:
    t = reg.nlargest(3, c)
    top_players[name] = [(n, float(v), int(g)) for n, v, g in zip(t.Name, t[c], t.Games)]
findings["top_players"] = top_players

lp = num(pd.read_csv(DATA / "leaders_players_averages.csv"), skip=("Name", "Team"))
lpq = lp[lp.Games >= 8].copy()
findings["league_players_qualified"] = len(lpq)
for c in ["RP", "D", "CP", "Cl", "T", "G", "M", "I50", "R50", "IP"]:
    lpq[f"{c}_rank"] = lpq[c].rank(ascending=False, method="min")
ours = lpq[lpq.Team == TEAM]
findings["league_ranks"] = {r.Name: {c: int(r[f"{c}_rank"]) for c in ["RP", "D", "CP", "Cl", "T", "G", "M", "I50", "R50", "IP"]}
                            for _, r in ours.sort_values("RP", ascending=False).head(8).iterrows()}
findings["league_top10_rp"] = lpq.nlargest(10, "RP")[["Name", "Team", "Games", "RP", "D", "G"]].to_dict("records")

fig, ax = plt.subplots(figsize=(10, 6.5))
t = reg.sort_values("RP").tail(15)
ax.barh(t.Name, t.RP, color=BLUE, height=0.7, edgecolor=SURF, linewidth=2)
for i, (v, g, d) in enumerate(zip(t.RP, t.Games, t.D)):
    ax.text(v + 1.5, i, f"{v:.0f}  ({int(g)} games, {d:.1f} disposals)", va="center", fontsize=8, color=INK2)
ax.set_xlim(0, t.RP.max() * 1.35)
ax.set_xlabel("Average ranking points per game (Premier Data's overall impact score)")
ax.set_title(f"{TEAM}: top 15 players by average impact (min. 5 games)")
ax.grid(axis="y", visible=False)
save(fig, "06_top_players.png")

# league context scatter: disposals vs ranking points, ours highlighted
fig, ax = plt.subplots(figsize=(10, 6))
oth = lpq[lpq.Team != TEAM]
ax.scatter(oth.D, oth.RP, s=22, color=GREY, alpha=0.7, label="Other GVL players", edgecolor=SURF, linewidth=0.8)
ax.scatter(ours.D, ours.RP, s=50, color=BLUE, label=TEAM, edgecolor=SURF, linewidth=1.5, zorder=3)
nudge = {"Kaedyn Napier": (-8, 8, "right"), "Liam Serra": (7, -4, "left")}
for _, r in ours.nlargest(8, "RP").iterrows():
    dx, dy, ha = nudge.get(r.Name, (6, 4, "left"))
    ax.annotate(r.Name, (r.D, r.RP), xytext=(dx, dy), textcoords="offset points", fontsize=8, color=INK, ha=ha)
ax.set_xlabel("Disposals per game")
ax.set_ylabel("Ranking points per game")
ax.set_title(f"Every GVL player with 8+ games: {TEAM} players in blue")
ax.legend(frameon=False, loc="upper left")
save(fig, "07_league_player_context.png")

# ---------------------------------------------------------------- per-game player form (if scraped)
mp_file = DATA / "match_player_stats.csv"
if mp_file.exists():
    mp = num(pd.read_csv(mp_file, dtype=str), skip=("Round", "Team", "Name"))
    mpu = mp[mp.Team.str.lower() == TEAM.lower()].copy()
    mpu = mpu[mpu.Round.str.isdigit()]
    mpu["Round"] = mpu.Round.astype(int)
    findings["match_player_rows"] = len(mpu)
    mpu = mpu.merge(us[["Round", "Result"]], on="Round", how="left")
    g = mpu.groupby("Name")
    form = pd.DataFrame({"Games": g.size(), "RP": g.RP.mean(), "RP_sd": g.RP.std(),
                         "RP_first": mpu[mpu.Round <= 9].groupby("Name").RP.mean(),
                         "RP_second": mpu[mpu.Round > 9].groupby("Name").RP.mean(),
                         "RP_win": mpu[mpu.Result == "W"].groupby("Name").RP.mean(),
                         "RP_loss": mpu[mpu.Result == "L"].groupby("Name").RP.mean()})
    form = form[form.Games >= 8].copy()
    form["Change"] = form.RP_second - form.RP_first
    form["CV"] = form.RP_sd / form.RP
    findings["improvers"] = form.dropna(subset=["Change"]).nlargest(5, "Change")[["Games", "RP_first", "RP_second", "Change"]].round(1).reset_index().to_dict("records")
    findings["decliners"] = form.dropna(subset=["Change"]).nsmallest(5, "Change")[["Games", "RP_first", "RP_second", "Change"]].round(1).reset_index().to_dict("records")
    findings["most_consistent"] = form[form.RP >= 80].nsmallest(5, "CV")[["Games", "RP", "RP_sd"]].round(1).reset_index().to_dict("records")
    findings["win_lift"] = (form.RP_win - form.RP_loss).dropna().sort_values(ascending=False).round(1).head(5).to_dict()
    best_games = mpu.nlargest(8, "RP")[["Round", "Name", "RP", "D", "G", "T", "Cl"]]
    findings["best_single_games"] = best_games.to_dict("records")

    fig, ax = plt.subplots(figsize=(10, 6.5))
    f = form.dropna(subset=["Change"]).sort_values("RP", ascending=False).head(14).sort_values("RP_second")
    y = np.arange(len(f))
    ax.hlines(y, f.RP_first, f.RP_second, color=GREY, linewidth=2)
    # First half drawn as a ring so a player with no change still shows both markers.
    ax.scatter(f.RP_first, y, s=110, facecolor="none", edgecolor=ORANGE, linewidth=2, label="Rounds 1-9 average", zorder=3)
    ax.scatter(f.RP_second, y, s=60, color=BLUE, label="Rounds 10-18 average", zorder=3, edgecolor=SURF, linewidth=1.5)
    ax.set_yticks(y)
    ax.set_yticklabels(f.index)
    ax.set_xlabel("Average ranking points per game")
    ax.set_title(f"Form shift: first half vs second half of the season\nTop 14 {TEAM} players by average ranking points (8+ games)")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    save(fig, "08_player_form_halves.png")

    # player comparison heatmap: top 12 players, key stats per game, shaded within each stat
    keys = [c for c in ["D", "K", "HB", "CP", "M", "Cl", "I50", "R50", "T", "G", "RP"] if c in mpu.columns]
    top12 = form.sort_values("RP", ascending=False).head(12).index
    hm = mpu[mpu.Name.isin(top12)].groupby("Name")[keys].mean().loc[top12]
    norm = (hm - hm.min()) / (hm.max() - hm.min())
    fig, ax = plt.subplots(figsize=(11, 6))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seqblue", ["#eef4fc", "#86b6ef", "#2a78d6", "#104281"])
    ax.imshow(norm.values, cmap=cmap, aspect="auto")
    for i in range(hm.shape[0]):
        for j in range(hm.shape[1]):
            ax.text(j, i, f"{hm.values[i, j]:.1f}", ha="center", va="center", fontsize=8,
                    color="white" if norm.values[i, j] > 0.55 else INK)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([labels.get(k, k) for k in keys], rotation=35, ha="right")
    ax.set_yticks(range(len(top12)))
    ax.set_yticklabels(top12)
    ax.grid(False)
    ax.set_title("Player comparison: per-game averages (darker = higher within that stat)")
    save(fig, "09_player_comparison.png")

Path("report/findings.json").write_text(json.dumps(findings, indent=1, default=str))
print(json.dumps(findings, indent=1, default=str)[:12000])
