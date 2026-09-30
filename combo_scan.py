import json, duckdb
import pandas as pd
STD = {"2016-07-01", "2018-07-01", "2020-07-01", "2022-07-01", "2024-07-01"}
con = duckdb.connect("data/qanat.duckdb", read_only=True)
rows = con.execute("""select run_id, alpha, rebalance, report from _qanat_backtests
    where status='ok' and live is not true order by run_id desc""").fetchall()
con.close()
S = {}
for run_id, alpha, reb, rep in rows:
    if reb != "5d":
        continue
    d = json.loads(rep)
    c = d["conditions"]
    sp = str(c.get("split"))[:10]
    if sp not in STD:
        continue
    key = alpha + " " + json.dumps(c.get("allocation"), sort_keys=True)
    for p in d["periods"]:
        a = str(p["as_of"])[:10]
        if a >= sp:
            S.setdefault(key, {}).setdefault(a, p["net"])

df = pd.DataFrame({k: pd.Series(v) for k, v in S.items()}).sort_index()
BASE = 'alpha_momentum+alpha_reversal {"momentum": 0.5, "reversal": 0.5}'
print(f"{'후보':<72}{'n':>5}{'Sharpe':>8}{'상관':>7}")
for k in df.columns:
    if k.startswith("alpha_momentum+alpha_reversal"):
        continue
    both = df[[BASE, k]].dropna()
    if len(both) < 100:
        continue
    x = df[k].dropna()
    print(f"{k[:70]:<72}{len(both):>5}{x.mean() / x.std():>8.4f}{both[BASE].corr(both[k]):>7.2f}")
