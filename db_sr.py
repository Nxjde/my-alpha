import json, math, statistics, duckdb
STD = {"2016-07-01", "2018-07-01", "2020-07-01", "2022-07-01", "2024-07-01"}

con = duckdb.connect("data/qanat.duckdb", read_only=True)
rows = con.execute("""select run_id, alpha, rebalance, report from _qanat_backtests
    where status='ok' and live is not true order by run_id desc""").fetchall()
con.close()

def days(reb):
    try:
        return int(str(reb).rstrip("d"))
    except ValueError:
        return None

G = {}
for run_id, alpha, reb, rep in rows:
    d = json.loads(rep)
    c = d["conditions"]
    sp = str(c.get("split"))[:10]
    if sp not in STD:
        continue
    per = sorted(d["periods"], key=lambda p: p["as_of"])
    oos = [p["net"] for p in per if str(p["as_of"])[:10] >= sp]
    key = (alpha, reb, json.dumps(c.get("allocation"), sort_keys=True))
    G.setdefault(key, {}).setdefault(sp, oos)

out = []
for (alpha, reb, alloc), folds in G.items():
    if len(folds) < 4:
        continue
    x = [r for sp in sorted(folds) for r in folds[sp]]
    sd = statistics.pstdev(x)
    dd = days(reb)
    if sd == 0 or dd is None:
        continue
    sr = statistics.mean(x) / sd * math.sqrt(5 / dd)   # 5일 주기 기준으로 환산
    out.append((sr, alpha, reb, alloc, len(folds), len(x)))

out.sort(reverse=True)
print(f"{'Sharpe(5d)':>10}  {'folds':>5} {'n':>4}  alpha | rebalance | allocation")
for sr, a, r, al, nf, n in out:
    print(f"{sr:>10.4f}  {nf:>5} {n:>4}  {a} | {r} | {al}")

v = [o[0] for o in out]
print(f"\n후보 수={len(v)}  min={min(v):.4f}  max={max(v):.4f}  sd={statistics.stdev(v):.4f}")
