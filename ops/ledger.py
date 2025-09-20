# ops/ledger.py
from __future__ import annotations
import os, json, time, sqlite3, pathlib, argparse, datetime as dt

KPI = pathlib.Path(".imu_runs/llm_kpis.jsonl")
DB  = pathlib.Path(".imu_runs/finops.db")

DDL = """
CREATE TABLE IF NOT EXISTS provider_daily(
  provider TEXT NOT NULL,
  day      TEXT NOT NULL,   -- YYYY-MM-DD (UTC)
  calls    INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL    NOT NULL DEFAULT 0.0,
  latency_ms_avg REAL NOT NULL DEFAULT 0.0,
  PRIMARY KEY(provider, day)
);
"""

def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))

def ingest(kpi_path: pathlib.Path = KPI, db_path: pathlib.Path = DB):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute(DDL)
    cur = con.cursor()

    # נטען כל ה-KPI ונאגד לפי provider+day
    agg = {}  # (provider, day) -> dict
    if kpi_path.exists():
        for ln in kpi_path.read_text(encoding="utf-8").splitlines():
            try:
                j = json.loads(ln)
            except Exception:
                continue
            p   = (j.get("provider") or "unknown")
            ts  = float(j.get("ts", time.time()))
            day = _day(ts)
            cost = float(j.get("cost_usd", j.get("cost", 0.0)) or 0.0)
            lat  = float(j.get("latency_ms", 0.0) or 0.0)
            k = (p, day)
            bucket = agg.setdefault(k, {"calls":0,"cost":0.0,"lat_sum":0.0})
            bucket["calls"] += 1
            bucket["cost"]  += cost
            bucket["lat_sum"] += lat

    # נשפוך ל-SQLite (UPSERT)
    for (prov, day), v in agg.items():
        calls = int(v["calls"])
        cost  = float(v["cost"])
        lat   = (v["lat_sum"]/calls) if calls else 0.0
        cur.execute("""
        INSERT INTO provider_daily(provider, day, calls, cost_usd, latency_ms_avg)
        VALUES(?,?,?,?,?)
        ON CONFLICT(provider,day) DO UPDATE SET
          calls = excluded.calls,
          cost_usd = excluded.cost_usd,
          latency_ms_avg = excluded.latency_ms_avg
        """, (prov, day, calls, cost, lat))

    con.commit(); con.close()

def report(days: int = 7, db_path: pathlib.Path = DB) -> dict:
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    # 7 ימים אחרונים (כולל היום)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    since = (dt.date.fromisoformat(today) - dt.timedelta(days=days-1)).isoformat()
    rows = cur.execute("""
      SELECT provider, day, calls, cost_usd, latency_ms_avg
        FROM provider_daily
       WHERE day >= ?
       ORDER BY day, provider
    """, (since,)).fetchall()
    con.close()
    out = {"days": days, "since": since, "today": today, "rows": [
        {"provider": r[0], "day": r[1], "calls": r[2], "cost_usd": round(r[3],6), "latency_ms_avg": round(r[4],1)}
        for r in rows
    ]}
    # סיכום לפי ספק
    prov = {}
    for r in out["rows"]:
        d = prov.setdefault(r["provider"], {"calls":0,"cost_usd":0.0})
        d["calls"]   += r["calls"]
        d["cost_usd"]+= r["cost_usd"]
    out["summary_by_provider"] = {k: {"calls": v["calls"], "cost_usd": round(v["cost_usd"],6)} for k,v in prov.items()}
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ingest","report"])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default="ops/ledger_report.json")
    args = ap.parse_args()

    if args.cmd == "ingest":
        ingest()
        print(json.dumps({"ok": True, "msg": "ingested"}, ensure_ascii=False))
    else:
        out = report(args.days)
        pathlib.Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
