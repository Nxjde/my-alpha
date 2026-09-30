import json
import numpy as np
S = json.load(open("pit_series.json"))
rng = np.random.default_rng(0)
for name in ("base_pit", "base_nofilter"):
    x = np.array(S[name])
    for L in (6, 12, 24):
        tr = np.array([x[i - L:i].mean() for i in range(L, len(x))])
        nx = x[L:]
        r = np.corrcoef(tr, nx)[0, 1]
        sh = rng.integers(len(tr) // 10, len(tr) - len(tr) // 10, 2000)
        perm = [np.corrcoef(np.roll(tr, int(s)), nx)[0, 1] for s in sh]
        p = (1 + sum(abs(v) >= abs(r) for v in perm)) / 2001
        print(f"{name:<14} L={L:>2} r={r:+.3f} p={p:.3f} n={len(nx)}")
