"""
research_worker.py

requests.jsonl의 pending 요청을 하나씩 꺼내서 Claude Code(헤드리스)로 실행.
RESEARCH_PROTOCOL.md를 반드시 따르도록 프롬프트에 강제 포함.
"""
import json
import subprocess
import os
from datetime import datetime, timezone

REQ_FILE = "requests.jsonl"
LOG_FILE = "worker.log"

def now():
    return datetime.now(timezone.utc).isoformat()

def load_requests():
    if not os.path.exists(REQ_FILE):
        return []
    out = []
    with open(REQ_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

def save_requests(reqs):
    with open(REQ_FILE, "w") as f:
        for r in reqs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{now()}] {msg}\n")
    print(msg, flush=True)

def build_prompt(user_text):
    return f"""너는 my-alpha 프로젝트의 리서치 워커다. 아래 절차를 반드시 지켜라:

1. RESEARCH_PROTOCOL.md를 먼저 읽고, 거기 적힌 Go/No-Go 기준, DSR 계산법,
   상관관계 검증 기준, 권한 경계를 그대로 따른다.
2. 절대로 하지 말 것: git push, KIS 실계좌/모의계좌 배분 변경, 실전 전환 결정.
   이런 게 필요하다고 판단되면 실행하지 말고 그 이유를 결과에 남겨라.
3. 검증이 끝나면 research_log.jsonl에 새 줄(JSON)을 append하라. 형식은
   기존 항목들과 동일하게: ts, idea, hypothesis, alpha_ids, method, result,
   verdict(GO/NO-GO/보류), reason.
4. 절대 임의로 기존 research_log.jsonl 내용을 덮어쓰거나 삭제하지 마라. append만.
5. 백테스트는 절대 nohup이나 백그라운드(&)로 던져놓고 세션을 끝내지 마라.
   qanat backtest는 foreground에서 완료될 때까지 기다렸다가(보통 구간당
   20~30분 소요, 5구간이면 최대 2시간까지 기다려도 된다) 그 결과를 직접
   확인한 뒤 research_log.jsonl에 기록하고 나서 세션을 끝내라.
   "백그라운드에서 진행 중이니 나중에 확인하겠다"는 식으로 끝내는 것은
   금지된 행동이다 -- 아무도 나중에 확인하러 오지 않는다.
6. 요청받은 범위만 돌려라. RESEARCH_PROTOCOL.md의 표준 5구간(split 2016-07,
   2018-07, 2020-07, 2022-07, 2024-07)이 기본이고, 요청에 없는 추가 구간이나
   추가 파라미터 조합은 절대 돌리지 마라. 시간이 남아도 마찬가지다.
7. 구간 하나가 끝날 때마다 그 결과를 research_log.jsonl에 중간 기록(verdict를
   "진행중"으로)해서, 세션이 중간에 죽어도 결과가 남게 하라. 마지막에 최종
   판정 줄을 하나 더 append하라.
8. 백테스트는 이미 DuckDB(_qanat_backtests 테이블)에 같은 조건의 결과가
   있는지 먼저 확인하고, 있으면 다시 돌리지 말고 그 결과를 재사용하라.

사람이 요청한 내용:
---
{user_text}
---

위 요청을 RESEARCH_PROTOCOL.md 절차대로 검증하고, research_log.jsonl에 결과를 기록해라.
"""

def process_one(req):
    log(f"처리 시작: {req['text'][:60]}...")
    prompt = build_prompt(req["text"])
    cmd = [
        "claude", "-p", prompt,
        "--permission-mode", "acceptEdits",
        "--output-format", "text",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=21600)
        req["status"] = "done" if result.returncode == 0 else "error"
        req["output_tail"] = (result.stdout or "")[-2000:]
        if result.returncode != 0:
            req["error_tail"] = (result.stderr or "")[-2000:]
        log(f"완료 (returncode={result.returncode})")
    except subprocess.TimeoutExpired:
        req["status"] = "timeout"
        log("타임아웃 (2시간 초과)")
    except Exception as e:
        req["status"] = "error"
        req["error_tail"] = str(e)
        log(f"예외 발생: {e}")
    req["processed_ts"] = now()
    return req

def main():
    reqs = load_requests()
    pending = [r for r in reqs if r.get("status") == "pending"]
    if not pending:
        log("처리할 요청 없음")
        return
    log(f"{len(pending)}개 pending 요청 발견")
    for i, req in enumerate(reqs):
        if req.get("status") == "pending":
            reqs[i] = process_one(req)
            save_requests(reqs)  # 매번 저장 (중간에 죽어도 진행상황 보존)
    log("이번 사이클 완료")

if __name__ == "__main__":
    main()
