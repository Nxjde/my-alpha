import duckdb, json
from datetime import datetime, timezone

STARTS = ["2016-06-20", "2018-06-21", "2020-06-21", "2022-06-21", "2024-06-21"]

con = duckdb.connect("data/qanat.duckdb", read_only=True)
rows = con.execute("""
    SELECT run_id, from_date, to_date, report FROM _qanat_backtests
    WHERE alpha = 'alpha_reversal_lb3' AND rebalance = '3d' AND status = 'ok'
    ORDER BY run_id DESC
""").fetchall()
con.close()

folds, seen = [], set()
for run_id, f, t, report in rows:
    if f not in STARTS or f in seen:
        continue
    seen.add(f)
    oos = json.loads(report)["segments"]["out_of_sample"]
    folds.append({"window_start": f, "run_id": run_id, "n": oos["periods"],
                  "net": round(oos["net"], 4), "hit_rate": round(oos["hit_rate"], 3)})
folds.sort(key=lambda x: x["window_start"])

n_pos = sum(1 for x in folds if x["net"] > 0)
entry = {
    "ts": datetime.now(timezone.utc).isoformat(),
    "idea": "reversal 알파 lookback=3, rebalance=3d 단독 5구간 Go/No-Go",
    "hypothesis": "lookback과 리밸런싱 주기를 3일로 맞추면 baseline(5일)보다 나은 단독 알파가 될 것",
    "alpha_ids": ["alpha_reversal_lb3"],
    "method": "5개 OOS 구간(split 2016-07/2018-07/2020-07/2022-07/2024-07) 단독 백테스트, 결과는 _qanat_backtests에서 직접 추출. net>0 조건만 평가(permutation 미실시: net>0 단계에서 이미 탈락)",
    "result": {"folds": folds, "n_positive": n_pos},
    "verdict": "GO" if n_pos >= 4 else "NO-GO",
    "chosen": None,
    "reason": f"5구간 중 net>0은 {n_pos}개로 기준(4/5) 미달. 헤드리스 워커가 2시간 타임아웃으로 죽어 자동 기록이 안 됐고, DB 이력에서 수동 복구해 기록함. 워커는 프로토콜 밖 추가 구간(2015-16, 2017-18, 2019-20)도 돌렸음(각 OOS -9.8%, -23.8%, +15.6%)."
}
with open("research_log.jsonl", "a") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
print(json.dumps(entry["result"], ensure_ascii=False, indent=1))
print("verdict:", entry["verdict"])
