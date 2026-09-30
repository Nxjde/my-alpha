import json
import numpy as np
from pit_lib import simulate, WINDOWS

S = {}
for name, kind, f in [("base_nofilter", "base", False), ("base_pit", "base", True),
                      ("mom_nofilter", "mom", False), ("mom_pit", "mom", True),
                      ("rev_nofilter", "rev", False), ("rev_pit", "rev", True)]:
    res = simulate(kind, f)
    x = np.array([v for lab in WINDOWS for v in res[lab]])
    S[name] = x.tolist()
    wins = [np.prod(1 + np.array(res[lab])) - 1 for lab in WINDOWS]
    print(f"{name:<14} n={len(x)} Sharpe={x.mean() / x.std():.4f} 누적={np.prod(1 + x):.2f}배 창별=" + "/".join(f"{w:+.1%}" for w in wins), flush=True)
json.dump(S, open("pit_series.json", "w"))
print("저장: pit_series.json")
