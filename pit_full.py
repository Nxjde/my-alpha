import json
import numpy as np
import pandas as pd
from pit_lib import C, WINDOWS, weights

def simulate_full(use_filter):
    res = {}
    for lab, split in WINDOWS.items():
        df = pd.read_csv(f"sweep_exports/1_1__{lab}.csv")
        prev, nets, n_is = pd.Series(dtype=float), [], 0
        for r in df.itertuples():
            a, d0, d1 = str(r.as_of)[:10], str(r.priced_from)[:10], str(r.priced_to)[:10]
            w = weights(a, use_filter, "base")
            p0, p1 = C.loc[pd.Timestamp(d0), w.index], C.loc[pd.Timestamp(d1), w.index]
            ok = p0.notna() & p1.notna() & (p0 > 0)
            g = float((w[ok] * (p1[ok] / p0[ok] - 1)).sum())
            keys = w.index.union(prev.index)
            turn = float((w.reindex(keys).fillna(0) - prev.reindex(keys).fillna(0)).abs().sum())
            nets.append(g - turn * 15 / 1e4)
            n_is += int(a < split)
            prev = w
        res[lab] = [nets, n_is]
    return res

out = {"nofilter": simulate_full(False), "pit": simulate_full(True)}
json.dump(out, open("pit_full.json", "w"))
S = json.load(open("pit_series.json"))
for key, name in (("nofilter", "base_nofilter"), ("pit", "base_pit")):
    oos = [x for lab in WINDOWS for x in out[key][lab][0][out[key][lab][1]:]]
    d = np.abs(np.array(oos) - np.array(S[name]))
    print(f"{key}: OOS {len(oos)}기간, pit_series.json과 최대 차이 {d.max():.2e}")
print("창별 IS 기간 수:", {lab: out["pit"][lab][1] for lab in WINDOWS})
