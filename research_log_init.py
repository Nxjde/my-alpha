"""research_log.jsonl 초기화 -- 지금까지의 주요 시도를 소급 기록"""
import json
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat()

entries = [
    {
        "ts": now(), "idea": "momentum+reversal 비율 스윕 (1:1~4:1)",
        "hypothesis": "momentum:reversal 배분 비율을 바꾸면 리스크/수익이 개선될 것",
        "alpha_ids": ["alpha_momentum", "alpha_reversal"],
        "method": "DSR (6 trials)",
        "result": {"1_1": {"sharpe": 0.1257, "dsr": 0.9945},
                   "2_1": {"sharpe": 0.1238, "dsr": 0.9937},
                   "2.5_1": {"sharpe": 0.1224, "dsr": 0.9931},
                   "3_1": {"sharpe": 0.1211, "dsr": 0.9926},
                   "3.5_1": {"sharpe": 0.1200, "dsr": 0.9921},
                   "4_1": {"sharpe": 0.1191, "dsr": 0.9916}},
        "verdict": "GO", "chosen": "1_1",
        "reason": "전 비율 DSR>0.99로 강건, 1:1이 Sharpe/최악구간 방어력 둘 다 최선"
    },
    {
        "ts": now(), "idea": "포트폴리오 vol targeting (이진 threshold 방식)",
        "hypothesis": "변동성 percentile 넘으면 비중 축소하면 MDD 개선될 것",
        "alpha_ids": ["alpha_momentum", "alpha_reversal"],
        "method": "threshold/scale_down 21개 조합 스윕",
        "result": {"best_sharpe": 0.1275, "baseline_sharpe": 0.1250},
        "verdict": "보류", "chosen": None,
        "reason": "최종수익 기준으론 전부 baseline보다 나쁨; MDD 기준으로는 일부 개선 확인 후 연속 스케일링으로 전환"
    },
    {
        "ts": now(), "idea": "포트폴리오 vol targeting (연속 스케일링, target_mult=0.7)",
        "hypothesis": "레버리지 없이 위기 시 축소 + 유휴자금을 다른 자산에 배분하면 개선될 것",
        "alpha_ids": ["alpha_momentum", "alpha_reversal"],
        "method": "vol targeting cap=[0.5,1.0] + 유휴자금 대안 3종 비교",
        "result": {
            "baseline": {"sharpe": 0.1250, "mdd": -0.295},
            "RP(무위험 3.35%)": {"sharpe": 0.1248, "mdd": -0.227},
            "low_vol 배분": {"sharpe": 0.1248, "mdd": -0.227, "corr_to_base": "0.23~0.34 (양의 상관, 기각)"},
        },
        "verdict": "보류", "chosen": None,
        "reason": "레버리지는 KIS 해외주식 100% 증거금 구조상 불가 확인. RP는 Sharpe 소폭+MDD 대폭 개선하나 수익 희생 있음. 최종 채택 여부 미결정"
    },
    {
        "ts": now(), "idea": "low_vol을 헤지/분산 소스로 추가",
        "hypothesis": "momentum+reversal과 낮은 상관관계일 것으로 기대",
        "alpha_ids": ["alpha_low_vol"],
        "method": "5구간 상관계수 + 단독 수익 확인",
        "result": {"corr_by_period": [0.258, 0.336, 0.229, 0.265, 0.236],
                   "standalone_net": [0.193, 0.218, 0.171, -0.106, 0.012]},
        "verdict": "NO-GO", "chosen": None,
        "reason": "전 구간 양의 상관관계 + 2021-23 마이너스 수익, 헤지 근거 없음"
    },
    {
        "ts": now(), "idea": "overnight_high를 헤지 소스로 추가",
        "hypothesis": "momentum+reversal과 낮은 상관관계일 것으로 기대",
        "alpha_ids": ["alpha_overnight_high"],
        "method": "5구간 상관계수 (이미 NO-GO였던 단독 알파 재활용)",
        "result": {"corr_by_period": [0.508, 0.252, 0.422, 0.212]},
        "verdict": "NO-GO", "chosen": None,
        "reason": "전 구간 양의 상관관계, 단독 알파 자체도 기존에 NO-GO"
    },
    {
        "ts": now(), "idea": "reversal_short를 헤지 소스로 추가",
        "hypothesis": "momentum+reversal과 낮은 상관관계일 것으로 기대",
        "alpha_ids": ["alpha_reversal_short"],
        "method": "5구간 상관계수 (이미 NO-GO였던 단독 알파 재활용)",
        "result": {"corr_by_period": [0.687, 0.762, 0.411, 0.732, 0.517]},
        "verdict": "NO-GO", "chosen": None,
        "reason": "전 구간 강한 양의 상관관계 (reversal 계열이라 당연한 결과), 단독 알파 자체도 기존에 NO-GO"
    },
]

with open("research_log.jsonl", "w") as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

print(f"{len(entries)}개 항목 기록 완료")
