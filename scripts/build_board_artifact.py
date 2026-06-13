"""Build the self-contained 'This Week' odds-board HTML from the latest odds snapshot.

Reads data/raw/odds_api_latest.json (produced by `python -m ingestion.live_odds`)
and writes this_week_dashboard.html at the project root. The HTML embeds the board
data so it renders with no server and no network access (used as a Cowork artifact).

Usage:
    uv run python scripts/build_board_artifact.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "odds_api_latest.json"
OUT = ROOT / "this_week_dashboard.html"


def _median(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def build_board(raw: list) -> dict:
    games = []
    for g in raw:
        home, away = g["home_team"], g["away_team"]
        ml_home, ml_away = [], []
        sp_home, sp_away = [], []
        tot_over, tot_under = [], []
        cons_sp, cons_tot = [], []
        for b in g["bookmakers"]:
            bk = b["title"]
            for m in b["markets"]:
                if m["key"] == "h2h":
                    for o in m["outcomes"]:
                        if o["name"] == home:
                            ml_home.append((o.get("price"), bk))
                        elif o["name"] == away:
                            ml_away.append((o.get("price"), bk))
                elif m["key"] == "spreads":
                    for o in m["outcomes"]:
                        pt, pr = o.get("point"), o.get("price")
                        if o["name"] == home:
                            sp_home.append((pt, pr, bk))
                            cons_sp.append(pt)
                        elif o["name"] == away:
                            sp_away.append((pt, pr, bk))
                elif m["key"] == "totals":
                    for o in m["outcomes"]:
                        pt, pr = o.get("point"), o.get("price")
                        if o["name"].lower() == "over":
                            tot_over.append((pt, pr, bk))
                            cons_tot.append(pt)
                        elif o["name"].lower() == "under":
                            tot_under.append((pt, pr, bk))

        # All three selectors are None-safe: a book may omit a price or point on
        # a given outcome, and None inside a max/min key raises TypeError.
        def best_ml(lst):
            lst = [(p, bk) for p, bk in lst if p is not None]
            if not lst:
                return None
            p, bk = max(lst, key=lambda x: x[0])
            return {"price": p, "book": bk}

        def best_pt(lst):  # most favorable point for the bettor, tiebreak best price
            lst = [t for t in lst if t[0] is not None]
            if not lst:
                return None
            pt, pr, bk = max(lst, key=lambda x: (x[0], -1e9 if x[1] is None else x[1]))
            return {"point": pt, "price": pr, "book": bk}

        def best_over(lst):  # over wants the lowest total, tiebreak best price
            lst = [t for t in lst if t[0] is not None]
            if not lst:
                return None
            pt, pr, bk = min(lst, key=lambda x: (x[0], 1e9 if x[1] is None else -x[1]))
            return {"point": pt, "price": pr, "book": bk}

        games.append({
            "home": home, "away": away, "commence": g["commence_time"],
            "n_books": len(g["bookmakers"]),
            "cons_spread_home": _median(cons_sp),
            "cons_total": _median(cons_tot),
            "best_ml_home": best_ml(ml_home),
            "best_ml_away": best_ml(ml_away),
            "best_spread_home": best_pt(sp_home),
            "best_spread_away": best_pt(sp_away),
            "best_over": best_over(tot_over),
            "best_under": best_pt(tot_under),
        })

    games.sort(key=lambda x: x["commence"])
    return {
        "generated_from": "data/raw/odds_api_latest.json",
        "snapshot_books_example": sorted({b["title"] for g in raw for b in g["bookmakers"]}),
        "num_games": len(games),
        "games": games,
    }


TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>This Week — NFL Odds Board</title>
<style>
:root{ color-scheme: light; }
*{box-sizing:border-box;}
body{margin:0;background:#f6f7f9;color:#1a1d23;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:14px;line-height:1.45;}
.wrap{max-width:1120px;margin:0 auto;padding:20px 18px 60px;}
h1{font-size:22px;margin:0 0 2px;font-weight:700;letter-spacing:-.01em;}
.sub{color:#5b6470;font-size:13px;margin:0 0 16px;}
.banner{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;border-radius:10px;padding:11px 14px;font-size:12.5px;margin:0 0 18px;}
.banner b{color:#7c2d12;}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 16px;}
.controls input,.controls select{font:inherit;padding:8px 11px;border:1px solid #d4d9e0;border-radius:8px;background:#fff;color:#1a1d23;}
.controls input{flex:1;min-width:180px;}
.count{color:#5b6470;font-size:12.5px;margin-left:auto;}
.card{background:#fff;border:1px solid #e4e8ed;border-radius:12px;padding:14px 16px;margin:0 0 12px;box-shadow:0 1px 2px rgba(16,24,40,.04);}
.chead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:10px;}
.match{font-size:15.5px;font-weight:650;}
.match .at{color:#9aa3af;font-weight:400;margin:0 5px;}
.kick{color:#5b6470;font-size:12px;white-space:nowrap;}
.cons{display:inline-flex;gap:8px;align-items:center;margin-top:2px;}
.pill{display:inline-block;background:#eef2f7;color:#384150;border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:550;}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}
@media(max-width:680px){.grid{grid-template-columns:1fr;}}
.mkt{border:1px solid #eceff3;border-radius:9px;padding:9px 10px;background:#fafbfc;}
.mkt h4{margin:0 0 7px;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:#8a93a0;font-weight:650;}
.side{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:4px 0;}
.side+.side{border-top:1px dashed #edf0f3;}
.team{font-size:12.5px;font-weight:550;color:#222831;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.price{font-variant-numeric:tabular-nums;font-weight:700;font-size:13px;}
.pos{color:#15803d;} .neg{color:#1f2937;}
.book{font-size:10.5px;color:#8a93a0;display:block;text-align:right;}
.foot{color:#8a93a0;font-size:11.5px;margin-top:24px;text-align:center;}
.empty{text-align:center;color:#8a93a0;padding:40px;}
</style>
</head>
<body>
<div class="wrap">
  <h1>This Week — NFL Odds Board</h1>
  <p class="sub" id="sub"></p>
  <div class="banner"><b>Line shopping, not picks.</b> Each cell shows the <b>best available price</b> for that side across all books in the snapshot, and which book offers it. Consensus = median line across books. This board surfaces price edge and the books to bet at — it is not a buy/sell signal. Past performance does not guarantee future results. Gamble responsibly.</div>

  <div class="controls">
    <input id="q" type="search" placeholder="Filter by team…" autocomplete="off">
    <select id="sort">
      <option value="kick">Sort: Kickoff</option>
      <option value="fav">Sort: Biggest favorite</option>
      <option value="total">Sort: Highest total</option>
      <option value="dogml">Sort: Best underdog ML</option>
    </select>
    <span class="count" id="count"></span>
  </div>

  <div id="list"></div>
  <p class="foot" id="foot"></p>
</div>

<script>
const BOARD = __DATA__;
const fmtPrice = p => p==null ? "—" : (p>0 ? "+"+p : ""+p);
const cls = p => p==null ? "" : (p>0 ? "pos":"neg");
function fmtKick(iso){
  const d=new Date(iso);
  return d.toLocaleString(undefined,{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
}
function spreadStr(pt){ if(pt==null) return "—"; return (pt>0?"+":"")+pt; }

function row(team, point, price, book){
  const pt = point!=null ? `<span class="pill">${spreadStr(point)}</span> ` : "";
  return `<div class="side"><span class="team">${team}</span>
    <span style="text-align:right">${pt}<span class="price ${cls(price)}">${fmtPrice(price)}</span>
    <span class="book">${book||""}</span></span></div>`;
}

function card(g){
  const cs = g.cons_spread_home;
  const favTeam = cs==null?null:(cs<0?g.home:g.away);
  const consPill = cs==null?"":`<span class="pill">${favTeam} ${spreadStr(cs<0?cs:-cs)}</span>`;
  const totPill = g.cons_total!=null?`<span class="pill">O/U ${g.cons_total}</span>`:"";
  const bsh=g.best_spread_home||{}, bsa=g.best_spread_away||{};
  const bmh=g.best_ml_home||{}, bma=g.best_ml_away||{};
  const bo=g.best_over||{}, bu=g.best_under||{};
  return `<div class="card">
    <div class="chead">
      <div>
        <div class="match">${g.away}<span class="at">at</span>${g.home}</div>
        <div class="cons">${consPill}${totPill}<span class="pill">${g.n_books} books</span></div>
      </div>
      <div class="kick">${fmtKick(g.commence)}</div>
    </div>
    <div class="grid">
      <div class="mkt"><h4>Moneyline</h4>
        ${row(g.away, null, bma.price, bma.book)}
        ${row(g.home, null, bmh.price, bmh.book)}
      </div>
      <div class="mkt"><h4>Spread</h4>
        ${row(g.away, bsa.point, bsa.price, bsa.book)}
        ${row(g.home, bsh.point, bsh.price, bsh.book)}
      </div>
      <div class="mkt"><h4>Total</h4>
        ${row("Over", bo.point, bo.price, bo.book)}
        ${row("Under", bu.point, bu.price, bu.book)}
      </div>
    </div>
  </div>`;
}

function render(){
  const q=document.getElementById('q').value.trim().toLowerCase();
  const sort=document.getElementById('sort').value;
  let gs=BOARD.games.filter(g=> !q || g.home.toLowerCase().includes(q) || g.away.toLowerCase().includes(q));
  if(sort==='kick') gs.sort((a,b)=>a.commence.localeCompare(b.commence));
  if(sort==='fav') gs.sort((a,b)=> (a.cons_spread_home==null?99:Math.abs(a.cons_spread_home)) - (b.cons_spread_home==null?99:Math.abs(b.cons_spread_home)) ).reverse();
  if(sort==='total') gs.sort((a,b)=> (b.cons_total||0)-(a.cons_total||0));
  if(sort==='dogml') gs.sort((a,b)=> Math.max(b.best_ml_home&&b.best_ml_home.price||-999,b.best_ml_away&&b.best_ml_away.price||-999) - Math.max(a.best_ml_home&&a.best_ml_home.price||-999,a.best_ml_away&&a.best_ml_away.price||-999));
  document.getElementById('list').innerHTML = gs.length? gs.map(card).join("") : '<div class="empty">No games match that filter.</div>';
  document.getElementById('count').textContent = gs.length+" of "+BOARD.games.length+" games";
}
document.getElementById('sub').textContent = BOARD.num_games+" upcoming games · books in snapshot: "+BOARD.snapshot_books_example.join(", ");
document.getElementById('foot').textContent = "Source: "+BOARD.generated_from+" · last refreshed "+(BOARD.refreshed_at||"")+" — snapshot is a point-in-time pull, not a live feed.";
document.getElementById('q').addEventListener('input',render);
document.getElementById('sort').addEventListener('change',render);
render();
</script>
</body>
</html>'''


def main():
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    board = build_board(raw)
    import datetime
    board["refreshed_at"] = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    html = TEMPLATE.replace("__DATA__", json.dumps(board, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} ({len(html)} bytes, {board['num_games']} games)")


if __name__ == "__main__":
    main()
