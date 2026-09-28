"""research dashboard v2 - 서버 로직 (화면은 dashboard_page.html)"""
from flask import Flask, jsonify, request, Response, abort
import json
import os
import statistics
from datetime import datetime, timezone

app = Flask(__name__)
LOG_FILE = "research_log.jsonl"
REQ_FILE = "requests.jsonl"
CACHE_FILE = "solo_cache.json"
PAGE_FILE = "dashboard_page.html"

SPLITS = ["2016-07-01", "2018-07-01", "2020-07-01", "2022-07-01", "2024-07-01"]
FOLD_LABELS = ["2015-17", "2017-19", "2019-21", "2021-23", "2023-25"]
RATIOS = ["1_1", "2_1", "2.5_1", "3_1", "3.5_1", "4_1"]
LABELS = {"low_vol": "low_vol 단독"}
for r in RATIOS:
    a, b = r.split("_")
    LABELS["mr_" + r] = "momentum:reversal %s:%s" % (a, b)

_cache = {"mtime": None, "data": None}


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def load_cache():
    m = os.path.getmtime(CACHE_FILE)
    if _cache["mtime"] != m:
        with open(CACHE_FILE) as f:
            _cache["data"] = json.load(f)
        _cache["mtime"] = m
    return _cache["data"]


def pmap(cache, key):
    return {p["as_of"]: p["net"] for p in cache[key]["periods"]}


def build_folds(key):
    """구간별 OOS (date, net) 리스트. 지원 안 하는 key면 None."""
    cache = load_cache()
    folds = []
    for i in range(5):
        if key.startswith("mr_"):
            a, b = key[3:].split("_")
            wm, wr = float(a), float(b)
            m = pmap(cache, "momentum_%d" % i)
            r = pmap(cache, "reversal_%d" % i)
            tot = wm + wr
            pts = [(d, (wm * m[d] + wr * r[d]) / tot) for d in sorted(set(m) & set(r))]
        elif key == "low_vol":
            pts = sorted(pmap(cache, "low_vol_%d" % i).items())
        else:
            return None
        folds.append([(d, n) for d, n in pts if d >= SPLITS[i]])
    return folds


def curve_keys(e):
    idea = e.get("idea", "")
    if idea.startswith("momentum+reversal 비율 스윕"):
        return ["mr_" + r for r in RATIOS]
    if "alpha_low_vol" in e.get("alpha_ids", []) and "헤지" in idea:
        return ["low_vol"]
    return []


@app.route("/api/log")
def api_log():
    out = []
    for i, e in enumerate(load_jsonl(LOG_FILE)):
        idea = e.get("idea", "")
        e["id"] = i
        e["supplement"] = idea.startswith("[정정]") or idea.startswith("[보강]")
        e["counted"] = (not e["supplement"]) and e.get("verdict") != "진행중"
        e["curves"] = [{"key": k, "label": LABELS.get(k, k)} for k in curve_keys(e)]
        out.append(e)
    return jsonify(out)


@app.route("/api/curve/<key>")
def api_curve(key):
    try:
        folds = build_folds(key)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500
    if folds is None:
        abort(404)
    curve, fold_out, nets = [], [], []
    eq, peak, mdd = 1.0, 1.0, 0.0
    for i, pts in enumerate(folds):
        if not pts:
            continue
        f_eq, f_peak, f_mdd = 1.0, 1.0, 0.0
        for d, n in pts:
            eq *= 1.0 + n
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1.0)
            f_eq *= 1.0 + n
            f_peak = max(f_peak, f_eq)
            f_mdd = min(f_mdd, f_eq / f_peak - 1.0)
            curve.append([d[:10], round(eq, 4)])
            nets.append(n)
        fold_out.append({"label": FOLD_LABELS[i], "net": round(f_eq - 1.0, 4),
                         "n": len(pts), "mdd": round(f_mdd, 4)})
    sd = statistics.pstdev(nets) if len(nets) > 1 else 0.0
    sharpe = statistics.mean(nets) / sd if sd > 0 else 0.0
    return jsonify({"key": key, "label": LABELS.get(key, key), "folds": fold_out,
                    "curve": curve, "sharpe": round(sharpe, 4), "mdd": round(mdd, 4),
                    "final": round(eq - 1.0, 4)})


@app.route("/api/requests")
def api_requests():
    return jsonify(load_jsonl(REQ_FILE))


@app.route("/api/submit", methods=["POST"])
def api_submit():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "text": text, "status": "pending"}
    with open(REQ_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return jsonify({"ok": True, "entry": entry})


@app.route("/")
def index():
    with open(PAGE_FILE, encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


@app.route("/app.js")
def appjs():
    with open("app.js", encoding="utf-8") as f:
        return Response(f.read(), mimetype="application/javascript")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
