# Qanat 미국 주식 알파 연구 — 현재 상태

## 배경
- 원래 BTCUSDT 15분봉 크립토 알고리즘 트레이딩 연구 중이었으나, 레짐/노이즈가 심해 decay가 빠르다는 한계를 느껴 미국 주식(S&P500)으로 피벗
- fidetolabs의 오픈소스 Qanat(agent-native 백테스트 워크플로우 엔진)을 AWS EC2(Amazon Linux 2023)에 설치해서 사용 중

## 인프라
- AWS EC2, Amazon Linux 2023, t3.small
- Qanat 설치: `python3.11 -m pip install --user qanat-fdtl` (Python 3.9는 미지원이라 3.11 별도 설치 필요했음)
- 프로젝트 경로: `~/my-alpha`

## 데이터
- S&P500 유니버스: GitHub `datasets/s-and-p-500-companies`의 constituents.csv 사용 (위키피디아 직접 파싱은 403 에러로 실패)
- 가격 데이터: yfinance로 503종목 + SPY, 10년치(2015-01-01~2026-09-11) 일봉
- `data/real_prices.csv`로 저장 후 Qanat의 `csv` 커넥터로 연결 (`connector: synthetic` → `connector: csv`로 qanat.yaml 수정)

## 핵심 발견
1. **momentum 알파(원본, 필터 없음)는 레짐 의존적**: 5개 구간(2015~2025, 3년씩) split sweep 결과:
   - 2015~2017: out-sample +31.4% (SPY +31.0%, 거의 알파 없음)
   - 2017~2019: out-sample **-26.7%** (SPY +21.9%, 큰 마이너스 알파) — 원인: PCG(파산 신청 후 급등) 물림 + 2018년 12월 급락장에서 방어주(PNW/DUK/O 등) 쏠림
   - 2019~2021: out-sample +84.4% (SPY +56.3%)
   - 2021~2023: out-sample +104.6% (SPY +27.7%)
   - 2023~2025: out-sample +113.5% (SPY +27.3%)
   - 승률 4/5, 평균 초과수익은 크지만 변동성이 매우 큼

2. **종목 레벨 필터는 효과가 없거나 역효과**:
   - 급락 필터, 절대모멘텀 필터, 변동성 상위10% 제외, SPY 200일/20일 레짐 필터 전부 시도
   - PCG 문제는 변동성 필터로 해결됐으나, 2017~2019 개선은 미미했고 다른 좋은 구간(2021~2023: +104.6%→-8.7%)을 크게 훼손
   - **결론: momentum의 종목선택 로직 자체를 필터로 고치려는 시도는 전부 실패하거나 부작용이 더 컸음**

3. **포트폴리오 레벨 분산(momentum + low_vol 조합)이 가장 효과적**:
   - `qanat backtest --alpha alpha_momentum,alpha_low_vol --allocation momentum=3,low_vol=1` (75:25)
     - 2017~2019: -26.7% → **-15.7%**
     - 5/5 구간 전부 플러스 (원본은 4/5)
   - `momentum=2,low_vol=1` (67:33): 2017~2019 **-11.9%**까지 개선, 다른 구간은 비례해서 더 희생
   - **결론: 필터링보다 알파 조합(분산)이 더 안전하고 효과적인 리스크 관리 방법**

## 현재 파일 상태 (중요 — 새 세션에서 꼭 확인)
- `steps/alpha_momentum.py`: **원본(필터 없음) 상태로 복원됨**
- `steps/alpha_momentum.py.bak` ~ `.bak5`: 각 실험 단계의 백업본 (참고용)
- `combo_sweep.py`: momentum+low_vol 조합 5구간 sweep 스크립트, 현재 `momentum=2,low_vol=1` 세팅 상태
- `split_sweep_long.py`: 순수 momentum 5구간 sweep 스크립트

## 다음 할 일 (TODO)
- [ ] momentum=1,low_vol=1(50:50) 등 다른 비율 테스트
- [ ] reversal, neutral_momentum도 같은 수준으로 깊게 검증 (SPY 비교, 5구간 sweep)
- [ ] rebalance 주기(현재 5d)를 10d, 20d로 바꿔 turnover/비용 구조 개선 여지 확인
- [ ] 검증 끝나면 Alpaca 또는 KIS 모의투자로 실전 검증 단계 이동
- [ ] Vibe-Trading의 Strategy Discovery Manager 아이디어(decay 자동 감지: rolling/baseline IC 비율, 연속 신호 기반 상태 전이) 참고해서 momentum 상태 자동 판정 로직 만들기

## 환경 정보
- EC2 퍼블릭 IP는 재부팅 시 바뀔 수 있음 — AWS 콘솔에서 매번 확인 필요
- SSH 키 파일: AWS.pem
- 접속: `ssh -i AWS.pem ec2-user@<현재IP>`

## [업데이트] 조합 비율 전체 실험 결과 (momentum + low_vol)

| 구간 | 순수momentum | 3:1(75:25) | 2:1(67:33) | 1:1(50:50) | SPY |
|---|---|---|---|---|---|
| 2015~2017 | +31.4% | +29.2% | +28.4% | +26.5% | +31.0% |
| 2017~2019 | -26.7% | -15.7% | -11.9% | -3.9% | +21.9% |
| 2019~2021 | +84.4% | +69.6% | +64.1% | +52.8% | +56.3% |
| 2021~2023 | +104.6% | +70.5% | +59.8% | +39.8% | +27.7% |
| 2023~2025 | +113.5% | +81.6% | +71.4% | +48.6% | +27.3% |

**결론: momentum=1,low_vol=1 (50:50)을 현재 최선의 조합으로 채택.**
- 최악 구간(2017~2019) 손실을 -26.7% → -3.9%까지 거의 해소
- 나머지 4개 구간 모두 SPY를 상당히 상회
- turnover도 감소해 비용 부담 완화

### 남은 TODO
- [ ] reversal, neutral_momentum도 momentum과 같은 수준으로 검증 (SPY 비교, 5구간 sweep)
- [ ] 1:1 조합이 3-알파 조합(momentum+low_vol+neutral_momentum 등)으로 더 개선되는지 확인
- [ ] rebalance 주기(5d→10d/20d) 조정 실험
- [ ] 검증 완료되면 Alpaca/KIS 모의투자로 이동

## [업데이트] reversal 알파 검증 — momentum과 거의 반대 패턴

| 구간 | reversal | momentum(원본) | SPY |
|---|---|---|---|
| 2015~2017 | +29.8% | +31.4% | +31.0% |
| 2017~2019 | **+127.3%** | -26.7% | +21.9% |
| 2019~2021 | +40.9% | +84.4% | +56.3% |
| 2021~2023 | +24.1% | +104.6% | +27.7% |
| 2023~2025 | -4.9% | +113.5% | +27.3% |

**핵심 발견: momentum이 최악이었던 2017~2019(-26.7%)에서 reversal은 최고(+127.3%), 
momentum이 최고였던 2023~2025(+113.5%)에서 reversal은 유일하게 마이너스(-4.9%).
momentum+low_vol보다 훨씬 강력한 헤지 관계로 보임 — 다음 세션에서 momentum+reversal 
조합(다양한 비율)을 5구간 sweep으로 검증할 것.**

### 다음 세션 시작 시 바로 할 일
- [ ] `qanat backtest --alpha alpha_momentum,alpha_reversal --allocation momentum=1,reversal=1` 등으로 5구간 sweep
- [ ] 이게 momentum+low_vol(1:1, 최선이었던 조합)보다 나은지 비교
- [ ] 좋으면 3-알파 조합(momentum+reversal+low_vol)도 시도
- [ ] neutral_momentum 알파도 아직 검증 안 됨 — 여유 되면 진행

## Session update (momentum+reversal combo validation)

**Correction to earlier assumption**: initially suspected `--allocation` (signal-blend)
caused a "netting loss" vs a true capital-split. Verified by running momentum-only and
reversal-only backtests separately and combining their per-period `net` values locally
with fixed-weight rebalancing (see `sleeve_combine.py`). Results matched `--allocation`
output almost exactly (e.g. 2017-19 out-of-sample at 3:1 was -1.0% via --allocation vs
-1.1% via sleeve combine). Conclusion: `--allocation` does NOT lose value to netting —
my earlier "expected value" comparison was wrong (simple arithmetic averaging of
compounded period returns, not valid math). qanat's blending is trustworthy.

**momentum:reversal ratio sweep, out-of-sample net by period**:

|
tail -40 STATE.md
git add STATE.md sleeve_combine.py momentum_reversal_sweep.py
git commit -m "momentum+reversal combo validation: sleeve combine confirms --allocation is correct, ratio sweep 1:1~4:1"
git push
Ctrl+C
git diff STATE.md | head -50
git checkout -- STATE.md
tail -5 STATE.md
cat >> STATE.md << 'EOF'

## 세션 업데이트 (momentum+reversal 조합 검증)

**이전 가설 정정**: `--allocation`(시그널 합성 방식)이 진짜 자본 분할 대비 "netting 손실"을
낸다고 처음엔 의심했음. momentum·reversal을 각각 단독으로 backtest 돌린 뒤, 두 결과의
period별 net을 코드에서 직접 비율대로 재조정하며 복리 합산해서 검증함 (`sleeve_combine.py`).
결과가 `--allocation` 출력과 거의 정확히 일치함 (예: 2017-19 out-of-sample, 3:1 비율에서
--allocation은 -1.0%, sleeve 합산은 -1.1%). 결론: `--allocation`은 netting으로 손실을
내지 않음 — 이전에 "기대값과 다르다"고 계산했던 건 계산 실수였음 (복리로 불어난 구간
수익률을 단순 산술평균 내는 건 애초에 틀린 계산법). qanat의 블렌딩 로직은 신뢰할 수 있음.

**momentum:reversal 비율 스윕, 구간별 out-of-sample net**:

| 비율 | 2017-19 | 2019-21 | 2021-23 | 2023-25 | 평균 |
|---|---|---|---|---|---|
| 1:1 | +31.9% | 68.1% | 64.8% | 47.7% | 49.1% |
| 2:1 | +9.0% | 75.0% | 78.5% | 68.3% | 52.8% |
| 2.5:1 | +3.1% | 76.8% | 82.3% | 74.5% | 53.9% |
| 3:1 | -1.1% | 78.0% | 85.2% | 79.2% | 54.8% |
| 3.5:1 | -4.3% | 78.9% | 87.4% | 82.9% | 55.5% |
| 4:1 | -6.8% | 79.6% | 89.2% | 85.8% | 56.1% |

트레이드오프: momentum 비중을 올릴수록 평균 수익은 계속 늘지만, 최악 구간(2017-19)
방어력은 계속 깎임. 최악 구간이 마이너스로 전환되는 지점은 2.5:1~3:1 사이.

**후보안**:
- 방어 우선: momentum=2.5,reversal=1 — 5구간 전부 플러스 유지, 평균 53.9%
  (momentum+low_vol(1:1) 기존안 평균 ~35.8%보다 훨씬 높음)
- 수익 우선: momentum=4,reversal=1 — 평균 최고(56.1%)지만 최악 구간이 -6.8%로 다시
  마이너스 (그래도 momentum 단독의 -26.7%보다는 훨씬 나음)

**다음 TODO**: 2.5:1과 4:1 후보 중 하나를 확정하기 전에, BTCUSDT 프로젝트 때 쓴
Go/No-Go 프레임워크 기준(permutation test, walk-forward)으로 유의성 검증 필요.
지금까지는 구간당 단일 in/out split 결과일 뿐, 통계적 검증은 아직 안 됨.

## Session update 2 (Go/No-Go validation of momentum+reversal ratios)

Applied the BTCUSDT project's Go/No-Go framework (adapted: 5 macro-regime periods as
folds instead of 4 walk-forward folds; permutation test on **gross only**, with
fees/slippage held fixed as a non-flippable drag, since flipping net's sign was found
to incorrectly let costs "become profit" under the null — this was a bug in the first
version of the test, fixed before these results). 2000 permutations per fold,
threshold p<0.05, pass requires positive net AND p<0.05 AND n>=20 periods; GO requires
4-of-5 folds passing.

**Result: all 5 tested ratios (1:1, 2.5:1, 3:1, 3.5:1, 4:1) passed GO (4-of-5 folds).**

| ratio | avg out-of-sample | 2017-19 net | 2017-19 p-value |
|---|---|---|---|
| 1:1 | 49.1% | +31.9% | 0.063 (near-significant) |
| 2.5:1 | 53.9% | +3.1% | 0.233 (not significant) |
| 3:1 | 54.8% | -1.1% | 0.274 (fold FAILS) |
| 3.5:1 | 55.5% | -4.3% | 0.314 (fold FAILS) |
| 4:1 | 56.1% | -6.8% | 0.347 (fold FAILS) |

**Key finding**: 1:1 is the only ratio with a near-significant directional edge in the
worst regime (2017-19). All higher momentum-weighted ratios gain average return but
lose statistical defensibility in that regime — the edge there becomes indistinguishable
from noise (p=0.23-0.35). This mirrors momentum-alone's core weakness (regime
dependency), so leaning too far toward momentum risks reintroducing the same problem
the reversal hedge was meant to solve.

**Tentative decision**: momentum=1,reversal=1 (1:1) as the primary candidate — it
sacrifices ~5-7pp of average return vs 3:1-4:1, but is the only ratio that statistically
defends the hedge's original purpose. 2.5:1-3:1 remain reasonable if betting that the
2015-2025 regime distribution repeats.

**Next TODO**: decide 1:1 vs 2.5:1+ based on risk preference; if proceeding, next
steps are (a) out-of-sample paper validation going forward, (b) checking transaction
cost sensitivity, (c) considering whether the permutation methodology itself needs
peer review (period-level gross-sign flipping is a reasonable but non-standard choice
vs. trade-level permutation used in the BTCUSDT project).

## Session update 3 (cost sensitivity check, momentum+reversal 1:1)

Tested how robust the 1:1 combo is to transaction cost assumptions by recomputing net
from cached turnover (fees/slippage = turnover * bps/10000), no backtest re-run needed.

| cost scenario | 5-fold positive | p<0.05 folds |
|---|---|---|
| baseline (5bps fee / 10bps slippage) | 5/5 | 4/5 |
| 1.5x (7.5/15bps) | 5/5 | 4/5 |
| 2x (10/20bps) | 5/5 | 4/5 |
| 3x (15/30bps) | 3/5 | 4/5 |
| retail-worst-case (10bps fee/30bps slippage) | 3/5 | 4/5 |

**Finding**: the combo tolerates up to 2x the baseline cost assumption while staying
positive in all 5 folds. At 3x cost (or slippage alone spiking to 30bps), the two
thinnest-margin regimes (2015-17, 2017-19) turn negative first — consistent with them
being the same regimes the reversal hedge exists to protect. p-values stay roughly
stable across cost scenarios (costs affect both real and permuted returns equally),
so the *direction* of the edge is cost-independent even though the *magnitude* is not.

**Conclusion**: momentum=1,reversal=1 is confirmed as the primary candidate — passes
Go/No-Go, and holds up to 2x realistic transaction costs. Baseline cost assumptions
(5bps/10bps) should still be validated against the actual broker's real fee/spread
before live deployment, especially if the universe includes lower-liquidity names.

**Next TODO**: (a) verify actual broker fee/spread against the 5bps/10bps baseline,
(b) check universe for low-liquidity names that could see slippage spike well above
30bps, (c) out-of-sample paper validation going forward.

## Session update 4 (paper validation automation set up)

Set up daily automation to start accumulating true out-of-sample live results for the
momentum=1,reversal=1 candidate:

- Found and fixed a corrupted `data/real_prices.csv`: 2,939 rows (all of 2015-2026,
  SPY only) had been appended earlier with a broken MultiIndex-column schema
  (14 columns instead of 7, empty ts/symbol fields). Confirmed the corruption did NOT
  affect any prior backtest results (only 1 stray row slipped through into
  `normalized__prices`; 504 symbols and full date range were intact throughout).
  `daily_update.py` now enforces a strict 7-column schema on every write, preventing
  recurrence.
- `daily_update.py`: pulls last 10 days of prices via yfinance, dedupes on
  (ts, symbol), appends safely. Installed `cronie` (not present by default on this
  AL2023 instance) and registered a crontab entry to run this
cd ~/my-alpha
cat >> STATE.md << 'EOF'

## Session update 4 (paper validation automation set up)

Set up daily automation to start accumulating true out-of-sample live results for the
momentum=1,reversal=1 candidate:

- Found and fixed a corrupted `data/real_prices.csv`: 2,939 rows (all of 2015-2026,
  SPY only) had been appended earlier with a broken MultiIndex-column schema
  (14 columns instead of 7, empty ts/symbol fields). Confirmed the corruption did NOT
  affect any prior backtest results (only 1 stray row slipped through into
  `normalized__prices`; 504 symbols and full date range were intact throughout).
  `daily_update.py` now enforces a strict 7-column schema on every write, preventing
  recurrence.
- `daily_update.py`: pulls last 10 days of prices via yfinance, dedupes on
  (ts, symbol), appends safely. Installed `cronie` (not present by default on this
  AL2023 instance) and registered a crontab entry to run this daily at 08:00 KST.
- `qanat.yaml` backtest block: `live: true`, `live_from: '2026-09-18'`, `split:
  '2026-09-18'` (data was current through 2026-09-18 at setup time).
- Crontab now runs, in sequence, daily at 08:00 KST: `daily_update.py` -> `qanat run`
  (refresh pipeline) -> `qanat backtest` on momentum+reversal(1:1) with the fixed
  split, appending JSON results to `logs/live_results.jsonl`.
- Verified the full chain works end to end with a manual dry run (from 2025-01-01,
  split 2026-09-18): 0 failures, in-sample net +82.5% over 124 periods, live/
  out-of-sample correctly empty (0 periods) since no data exists past the split yet.
  This is expected -- the count should start growing as new days accumulate.

**Next TODO**: let this run for several weeks to accumulate genuine live periods,
then check `logs/live_results.jsonl` growth and whether live out-of-sample net stays
consistent with the historical backtest distribution. Also still pending from earlier
sessions: (a) verify actual broker fee/spread against the 5bps/10bps baseline, (b)
check universe for low-liquidity names that could see slippage spike well above 30bps.

## Session update 5 (reversal_short lookback=1 검증)

alpha_reversal_short (lookback=1, 사실상 매일 리밸런싱) 단독 Go/No-Go 검증 결과:
- 0/5
cd ~/my-alpha
cat >> STATE.md << 'EOF'

## Session update 5 (reversal_short lookback=1 검증)

alpha_reversal_short (lookback=1, 사실상 매일 리밸런싱) 단독 Go/No-Go 검증 결과:
- 0/5 p<0.05, 2/5 positive, 0/5 full-pass → NO-GO
- lookback=5 reversal 대비 수익이 크게 줄고, 통계적 유의성 완전히 사라짐
- 결론: 매일 리밸런싱 비용(수수료+슬리피지)이 1일 reversal 신호를 잡아먹음

**다음 선택지**:
- (A) lookback=2~4 스윕으로 최단 유효 lookback 탐색
- (B) 단기 전략 포기, momentum+reversal(1:1) 5일 주기에만 집중

## Session update 6 (Qanat 0.2.0 업그레이드)

- qanat-fdtl 0.1.3 -> 0.2.0 업그레이드 (pip install --user --upgrade qanat-fdtl)
- 0.2.0 변경사항 중 해당 프로젝트에 영향 있던 버그: 알파가 2개 이상인 프로젝트에서
  live scoring이 어떤 알파를 채점할지 못 정해 조용히 계속 실패 재시도하던 버그 ->
  0.2.0부터 `live_alphas:`가 없으면 에러를 내고 멈추도록 변경됨
- qanat.yaml backtest 블록에 `live_alphas: [momentum, reversal]` 추가
- 수동 검증: daily_update.py -> qanat run -> qanat backtest 전체 체인 에러 없이 통과,
  logs/live_results.jsonl에 2026-09-21까지 정상 반영 확인 (failures: [])
- 크론탭(08:00 KST 자동 실행)은 변경 없이 그대로 유지, 정상 작동 확인

**다음 단계**: momentum+reversal(1:1) 모의투자(paper trading) 연결 착수

## Session update 7 (KIS 모의투자 연결, 첫 리밸런싱 실행)

- KIS Developers에서 App Key/Secret 발급, 모의투자 계좌 연결 (CANO=50213721, ACNT_PRDT_CD=01)
- kis_client.py 작성: 토큰 캐싱(.kis_token_cache.json), 해외주식 잔고/현금/시세 조회,
  지정가 주문. 모든 호출에 공통 재시도(3회, 1s/2s 백오프) 적용 -- 모의투자 서버가
  간헐적으로 500을 뱉는 게 관찰돼서 필요했음
- rebalance_paper.py 작성: data/qanat.duckdb의 weights__momentum, weights__reversal
  최신 as_of를 읽어 qanat.backtest.combine()과 동일한 로직(0.5/0.5 섞고 재정규화)으로
  목표 포트폴리오 계산 -> 현재 보유와 diff -> 최소거래금액($5) 이상만 주문
- 실제 duckdb 스키마는 `weights.<name>`이 아니라 `main.weights__<name>` (이중언더스코어)
  였음 -- 이후 유사 스크립트 작성 시 참고
- 종목별 거래소(NASDAQ/NYSE/AMEX)는 자동 판별 후 캐싱 (S&P500엔 나스닥 외 종목도 섞여있음)
- 2026-09-24 기준 8종목(momentum 4 + reversal 4, 겹침 없음) 전량 매수 체결 완료.
  초기 $100,000 중 $87,389 현금 + $12,460 보유평가로 배분

**다음 단계**: 며칠 뒤 리밸런싱 주기(20d 등 알파 rebalance 설정)에 맞춰 재실행 필요,
cron에 rebalance_paper.py 자동 실행 추가 여부 결정 필요

## 세션 업데이트 (momentum+reversal 비율 스윕 — Deflated Sharpe Ratio 검증)

**목적**: 이전 세션에서 나온 momentum:reversal 비율 스윕(1:1~4:1) 결과가 "6개 후보 중
가장 좋아 보이는 걸 골랐다"는 선택편향(multiple testing) 문제를 갖고 있어, López de Prado의
Deflated Sharpe Ratio(DSR)로 재검증함.

**방법**: 6개 비율(1:1, 2:1, 2.5:1, 3:1, 3.5:1, 4:1) × 4구간(2017-19, 2019-21, 2021-23,
2023-25)의 out-of-sample 리밸런싱 수익률(5일 주기)을 이어붙여 비율별 434개 관측치로
Sharpe·왜도·첨도를 계산하고, 6-trial 선택편향을 보정한 DSR을 산출함 (`dsr_sweep_resume.py`,
`dsr_calc.py`, 원본 pnl은 `sweep_exports/*.csv`에 보존).

**결과**:

| 비율 | out-of-sample Sharpe | DSR |
|---|---|---|
| 1:1 | 0.1257 | 0.9945 |
| 2:1 | 0.1238 | 0.9937 |
| 2.5:1 | 0.1224 | 0.9931 |
| 3:1 | 0.1211 | 0.9926 |
| 3.5:1 | 0.1200 | 0.9921 |
| 4:1 | 0.1191 | 0.9916 |

6개 비율 모두 DSR 0.99 이상 — 선택편향을 보정해도 momentum+reversal 조합은 통계적으로
강건한 알파임을 확인함. 또한 Sharpe 기준으로도 1:1이 6개 중 가장 우수(momentum 비중을
올릴수록 out-of-sample Sharpe가 단조 감소)해, 이전에 "최악 레짐 방어력" 기준으로 선택했던
1:1이 위험조정수익 기준으로도 최선임이 재확인됨.

**결론**: 1:1 비율(현재 KIS 모의투자 라이브 설정)을 최종 확정.

**인프라 메모**: 이번 스윕 과정에서 `qanat.duckdb`가 반복된 `--force` 백테스트로 16GB까지
재차 부풀어(과거 19GB 이슈와 동일 패턴) EXPORT/IMPORT로 104MB까지 재압축함. 2코어(t3.small)
한계 내에서 프로젝트 폴더를 reflink 복제(`cp --reflink=auto`)해 2-워커 병렬 처리로 스윕
시간을 단축함. 향후 대규모 스윕 시 (1) 사전에 `qanat.duckdb` 크기 점검, (2) 프로세스는
반드시 `nohup ... & disown`으로 완전히 분리해 실행할 것 (tmux 세션 내 직접 실행도
안전하지만, Ctrl+C 등 시그널이 실수로 자식 프로세스에 전달되면 조용히 죽을 수 있음을 확인).

## 세션 정리 (9/26~9/28): DSR 검증 · 오버레이 탐색 · 리서치 자동화 구축

**확정**
- momentum:reversal 1:1 유지. 6개 비율(1:1~4:1) 스윕 DSR 모두 0.99 이상, out-of-sample Sharpe도 1:1이 최선(0.1257).
- 단, 이 DSR은 이번 스윕 6개만 기준으로 계산함. 프로젝트 전체 누적 시도 횟수(vol targeting 21+21조합, 헤지 후보 3종, lookback 실험 등)는 반영 안 됨 -> 실제 DSR은 이보다 낮을 수 있음.
- KIS 해외주식(미국)은 매매증거금 100%라 레버리지 불가. 레버리지 오버레이는 배제.

**기각 (research_log.jsonl 참조)**
- 헤지/분산 소스: low_vol, overnight_high, reversal_short 모두 momentum+reversal과 양의 상관 + 단독 수익 부진 -> NO-GO.
- reversal lookback=2, lookback=3(rebalance 3d) 단독 검증: 5구간 중 net>0가 각각 1개, 2개 -> NO-GO.

**보류 (채택 전 추가 검증 필요)**
- vol targeting(target_mult=0.7, 레버리지 없음) + 유휴자금 RP(연 3.35%): avg_net 38.1%, Sharpe 0.1314, worst MDD -19.2% (baseline 49.1% / 0.1250 / -29.5%). 위험조정수익 기준으론 유망하나 목표변동성 배수(0.6/0.8) 안정성과 누적 M 반영 DSR 확인 전까지 미채택.
- 주의: 초기 장부에 RP 수치가 low_vol 값(0.1248 / -22.7%)으로 잘못 기록됐다가 정정 항목으로 바로잡음. 장부는 append-only.

**인프라**
- 리서치 자동화: EC2 Flask 대시보드 + Windows Electron 앱 + research_worker.py(Claude Code 헤드리스). 권한은 .claude/settings.json(allow/deny) + hooks/guard_bash.py(git push, nohup/&, run_in_background, 실계좌 관련 차단).
- qanat.duckdb는 --force 반복 실행으로 dead page가 쌓여 5.3GB까지 부풀었다가 EXPORT/IMPORT로 약 100MB로 압축. 대규모 스윕 뒤에는 크기를 점검하고 재압축할 것.
- 서버 시간대는 UTC (크론 0 8 * * * = 17:00 KST).
- 워커 교훈: 타임아웃 2시간에 죽은 원인은 요청 밖 구간을 추가로 돌린 것. 프롬프트에 범위 제한과 구간별 중간 기록 규칙 추가함.

**미검증 주장 (다음 세션에서 직접 확인할 후보)**
- 워커가 만든 스크립트(reversal_lb3_3d_compute.py, 커밋 제외)의 주석에 "qanat backtest에서 --from/--to가 약 2년을 넘는 단일 호출에 3d rebalance를 쓰면 20개 기간 이후 as_of가 모두 스킵된다"는 엔진 버그 주장이 있음. 워커가 임시 경로(/tmp)의 출력 파일에 의존해 재현 불가하고 아직 아무도 검증하지 않음. 사실이라면 3d 같은 짧은 리밸런싱 주기 실험 전반에 영향이 있으므로 확인 필요.
- 이 때문에 lb3 검증은 구간을 약 1.5년(OOS 절반)으로 쪼개 돌렸음. DB 복구값과 워커 결과 파일의 net/n이 정확히 일치하는 것까지만 확인됨.

## 세션 업데이트 (9/28): vol targeting + RP 검증 및 DSR 재산출

### vol targeting(레버리지 없음) + 유휴자금 RP
- 기존 38.1% / Sharpe 0.1314 / MDD -19.2%는 그대로 재현됨 (baseline 49.1% / 0.1250 / -29.5%, 5구간 543기간)
- 발견한 문제 3가지: (1) target_vol이 전 구간(OOS 포함) 평균 변동성이라 look-ahead, (2) RP 3.35%(2026년 고시금리)를 제로금리 구간(2015~2021)에도 소급 적용, (3) 스케일 변경 비용 미반영
- look-ahead 제거(구간별 IS 변동성으로 target 설정, 0.7, RP 3.35%): 40.4% / 0.1301 / MDD -22.8%. 비용 15bps/단위 반영 시 39.7% / 0.1284 / -22.9%
- 배수 0.5~1.0 안정성: Sharpe 방향이 두 가정에서 반대(global은 배수 낮을수록, insample은 높을수록 개선)이고 표면 전체가 0.126~0.133으로 평평함. 낙폭과 수익만 배수에 단조 반응 (insample RP 3.35%: 0.5는 MDD -16.7%/net 31.1%, 1.0은 MDD -27.5%/net 47.8%)
- RP 0%에서는 Sharpe가 baseline과 거의 같음(insample 0.1192~0.1293). Sharpe 개선의 대부분은 RP 이자 효과
- 짝지은 부트스트랩(블록 10, 2000회): dSharpe 95% CI RP 3.35% [-0.0136, +0.0240] (P(d<=0)=0.31), RP 0% [-0.0168, +0.0205] (P=0.44). 둘 다 0 포함
- 결론: Sharpe 개선 근거 없음(NO-GO). 재현되는 사실은 "낙폭 약 7%p 감소 / 평균 수익 약 9%p 감소" 트레이드오프뿐. 이건 성과 개선이 아니라 위험 선호 문제이며 라이브 배분 반영은 한서가 직접 판단

### DSR 재산출 (이전 "6개 비율 DSR 0.99 이상 → 1:1 확정" 정정)
- 이전 DSR은 sd_SR=0.0025(비율 6개 변형의 산포)를 썼음. 같은 아이디어의 변형끼리는 Sharpe가 거의 안 움직여서 다중검정 보정이 거의 작동하지 않았음
- data/qanat.duckdb의 _qanat_backtests에서 표준 5구간 중 4개 이상 있는 후보 21개의 OOS 수익률을 뽑아 sd_SR 재산출 (5일 주기로 환산, 기간 독립 가정). baseline은 DB 1:1 블렌드(n=543, Sharpe 0.1257)
- baseline DSR: 전체 21개 sd_SR 0.0940 -> 0.101(M=21) / 0.003(M=115). 5일 주기 13개만 sd_SR 0.0314 -> 0.953(M=13) / 0.850(M=115). 표본 노이즈 기준 sd_SR 0.0430 -> 0.842(M=21) / 0.635(M=115)
- 0.95를 넘는 칸은 "5일 주기만, M=13" 하나뿐(0.953)이고, 결과를 본 뒤 고른 부분집합이라 통과로 보지 않음. 전체 21개의 sd는 1일 주기 후보(Sharpe -0.15, -0.22)가 키운 값이라 과대일 수 있음
- 결론: Sharpe>0(t 약 2.8)은 분명하지만 다중검정 보정 후 유의성은 가정에 좌우되어 미확정
- 장부에 없던 시도 발견: alpha_reversal_lb4(5회), alpha_overnight_low(1회). DB 성공 설정은 92개(overnight_high 25, lb3 15, momentum+reversal 11, reversal_short 10 등)
- 비율 블렌드끼리 상관이 커서 유효 독립 시도 수는 M보다 작음(미계산)

### 다음 할 일
- [ ] logs/live_results.jsonl의 라이브 paper 결과가 쌓이면 진짜 OOS로 재평가 (DSR 가정 논쟁이 필요 없는 가장 깨끗한 증거)
- [ ] (선택) 후보 상관을 반영한 유효 시도 수 M_eff 계산 (가정이 들어가서 확정은 못 함)
- [ ] (선택) RP 금리를 시계열(예: 3개월 T-bill)로 바꾼 낙폭-수익 트레이드오프 재계산. Sharpe 결론이 이미 "구분 불가"라 우선순위 낮음
- [ ] 워커의 "3d rebalance + 2년 초과 단일 호출 시 as_of 스킵" 엔진 버그 주장은 아직 미검증. 사실이면 짧은 주기 실험 전반(lb2/lb3, 3d, overnight_high 3d/4d)의 Sharpe에 영향

### 이번 세션 파일
- vol_robust.py (배수 x RP 스윕, global vs insample, 스케일 변경 비용)
- vol_robust_dsr.py (M x sd_SR DSR 격자, 짝지은 부트스트랩)
- sd_sr.py, db_sr.py, dsr_db.py, dsr_final.py (sd_SR 산출 및 baseline DSR)
- research_log.jsonl 13줄로 증가 (추가 3건: 검증, DSR 보강, DSR 정정)
- 라이브 배분 변경과 git push는 한서가 직접 수행

## 세션 업데이트 (9/28): 누적 곡선 형태 분석 (momentum+reversal 1:1, 표준 4구간 OOS 434기간을 이어 붙인 곡선)
- 뒤로 갈수록 가팔라 보이는 건 대부분 복리 효과. 구간 누적은 32.3/68.6/65.4/48.0%, 이어 붙이면 약 5.46배. 로그 기준 구간 성장은 0.28/0.52/0.50/0.39로 뒤로 갈수록 커지지 않음(2019-23이 최대, 2023-25에서 완만)
- 기간당 평균 net은 0.31/0.54/0.56/0.42%로 국면 효과는 작음. 27기간(약 4.5개월) 블록 17개의 로그 성장 합은 1.698
- 성장이 고르지 않음: 두 블록(271~297기간 0.501, 406~432기간 0.284)이 전체 로그 성장의 약 46%, 나머지 15개 블록 평균 약 0.06. 음수 블록 55~81(-0.097), 190~270(3블록 합 -0.161, 약 1년 안팎 무수익). 라이브 초기 몇 달이 횡보·마이너스여도 이 분포에서는 흔한 일이라 그것만으로 전략 붕괴로 판단하지 않고, 반대로 좋다고 검증된 것도 아님
- 주의: 4개 OOS 창을 이어 붙인 가상 곡선이라 창 경계 블록은 두 창이 섞임. 대시보드 그래프가 구간을 이어 붙이는지는 미확인
- momentum 단독(같은 4창, 캐시): 누적 5.90배(로그 1.775), 창별 -26.7/84.4/104.6/113.5%, 창별 기간당 평균 net -0.22/0.70/0.79/0.82%로 뒤로 갈수록 상승(국면 의존). 상위 2블록 비중 73%(블렌드 46%), 최악 블록 -0.240(블렌드 -0.097). 블렌드와 큰 블록이 같은 시기(271~297, 406~432기간)라 두 전략의 이익이 같은 두 시기에 몰림. 블렌드는 첫 창 손실을 막는 대신 그 두 시기에 momentum의 약 70%/50%만 가져감. 총성장은 비슷(5.46배 vs 5.90배)하지만 블렌드가 경로가 훨씬 매끄러움(Sharpe 0.1258 vs 0.1076)
- 큰 블록의 날짜: 블록 11(271~297기간)=2023-03-27~2023-08-04, 블록 16(406~432기간)=2025-08-08~2025-12-16. 둘 다 최근 3년 안이며 가장 오래된 창(2017-19)에는 이런 블록이 없음. 두 시기의 SPY 수익률 확인은 대기 중
- 큰 블록의 날짜: 블록 11(271~297기간)=2023-03-27~2023-08-04, 블록 16(406~432기간)=2025-08-08~2025-12-16. 둘 다 최근 3년 안이며 가장 오래된 창(2017-19)에는 이런 블록이 없음. 두 시기의 SPY 수익률 확인은 대기 중
- 종목별 기여(block_check.py, 기여=비중x기간수익률의 단순 합): 블록 11은 CVNA +0.286, SMCI +0.155, APP +0.050 등으로 상위 3종목 85%(CVNA 단독 약 50%), 블록 16은 SNDK +0.159, LITE +0.102, CIEN +0.031 등으로 상위 3종목 86%. 큰 급등 블록이 소수 종목(4+4종목 집중 보유 구조) 의존이라는 확인. 라이브 성과도 몇 개 종목에 크게 좌우될 것으로 예상하며, 초기 몇 달 결과로 전략을 판단하지 않는다. top_n 변경은 새 시도이므로 별도 결정 사항

## 정정 (9/28): 생존편향 발견 - 이전 백테스트 수치는 부풀려진 값
- universes/sp500.csv의 from/to가 504종목 전부 비어 있어 현재 구성종목이 2015년부터 후보로 쓰임. 원본 sp500_raw.csv의 Date added로 편입 전 종목을 뺀 재구성(pit_check.py, 4창 434기간)에서 baseline Sharpe 0.1259 -> 0.0734, 누적 5.46배 -> 2.09배, 창별 +32/+69/+65/+48% -> +8/+72/-1/+13%
- 큰 블록의 상위 기여 종목(SMCI, CVNA, PLTR, APP, ECHO, LITE, RDDT, CIEN)은 해당 시점 지수 편입 전이라 필터 후 보유 0회. SNDK는 4회, WDC는 27회 유지
- 한계: 지수 제외/상장폐지 종목은 데이터에 없어 복원 불가. 실제 성과는 필터 후 값보다 낮을 수 있음
- 영향: 위 세션들의 baseline Sharpe, DSR, vol targeting, 익절 검증, 조합 후보 스캔, 시가/종가 진입 비교, 곡선 형태 분석은 전부 필터 없는 유니버스 위 결과. 수치 재계산 필요, 결론 방향은 재검증 전이라 확정하지 않음
- KIS 라이브는 현재 구성종목을 그때그때 쓰므로 이 편향이 없음. 라이브 기대치는 필터 후 수치에 가까울 것으로 추정

## 코인 15분봉 사전 검증 (9/28, ~/my-alpha/crypto/, 주식 라이브와 분리)
- 데이터: Binance USDT-M BTCUSDT 15분봉 2020-01~2026-08(233,760행, 결측 0). 폴드 4개(각 약 20개월), 신호는 종가·체결은 다음 봉 시가, 왕복 0.08%(2배도), 통과=net>0 & permutation p<0.05 & 트레이드 100+, 4폴드 중 3개 이상. 펀딩비 미반영
- 후보 3개 전부 NO-GO: 숏 전용 변동성 추세(0/4, net -53~-81%), 롱/숏 대칭(0/4, -71~-80%), 변동성 수축 돌파 숏(1/4, 폴드3만 +2.3% p=0.033이나 2x 비용에서 -9.9%). 후보 1, 2는 폴드당 800~1,700 매매로 비용이 지배, p값 0.3~0.55로 타이밍 우위 없음
- 결론: 15분봉 단일 자산에서는 이전 20개+ 전략과 같은 결과. 시도 +3. 재시도한다면 규칙 튜닝이 아니라 구조 변경(저빈도, 다중 코인 단면)으로 별도 결정

## momentum+reversal(1:1) 라이브 조합, PIT필터 표준 5구간 Go/No-Go 재검증 -> 판정 뒤집힘 (NO-GO)

**배경**: 9/28 세션 초반에 생존편향(현재 S&P500 구성종목을 과거 구간에도 후보로 씀)을 발견했지만,
그 재계산은 4구간(2017-19~2023-25)·상관/단독Sharpe 게이트 방식이었고, 원래 GO 판정을 냈던
`go_no_go_validate_v2.py`의 실제 기준(permutation test, 5구간, 4/5 pass)으로는 아직 재검증한
적이 없었음. 현재 KIS 모의투자에 실배분 중인 조합이라 우선순위가 가장 높다고 판단해 이번 세션에서
그 재검증을 수행함(`pit_baseline_5fold.py`).

**방법**: PIT 필터(편입일 이전 종목 제외) 신호 재현 로직은 이전 세션에서 실제 qanat 결과와
diff=0으로 검증된 것과 동일. 표준 5구간(split 2016/2018/2020/2022/2024-07-01) 전부 사용 —
기존 4구간 재구성에 없던 2015-17을 `qanat.duckdb`의 기존 백테스트 리포트(run_id
1789780400947923, 재실행 없음)에서 추출해 추가. permutation test(2000회, gross 부호만 반전,
비용 고정)까지 포함해 원래 GO 판정과 동일한 기준으로 비교.

**결과**: 필터 없이 같은 계산을 재현하면 4/5 pass로 기존 GO가 그대로 재현됨(방법론 검증 통과).
PIT 필터 적용 시 2/5만 pass(2015-17 p=0.006, 2019-21 p=0.007; 2017-19/2021-23/2023-25는
유의성 상실, 2021-23은 net도 마이너스) — **GO 기준(4/5) 미달로 NO-GO**. 2021-23·2023-25에서
유의성이 사라지는 건, 이전 세션에서 확인된 "수익 기여 상위 종목이 당시 지수 미편입"이었던 구간과
일치함.

**결론**: 현재 KIS 모의투자 라이브 배분(momentum+reversal 1:1)의 근거였던 GO 판정(2026-09-27)은
생존편향이 섞인 데이터 위에서 나온 것이고, 올바른 유니버스로 재검증하면 NO-GO. 라이브 배분 변경이나
실전 전환 판단은 권한 경계 밖이라 이 세션에서 직접 하지 않음 — **한서 직접 판단 필요**.
research_log.jsonl에 진행중 5줄 + 최종 NO-GO 1줄 기록.

**다음 할 일**: 라이브 배분 유지/중단 여부 결정, 축적 중인 실제 paper 결과와 이번 재계산치 대조,
(선택) PIT 필터 기준으로 momentum 단독/reversal 단독 등 다른 GO였던 후보도 같은 기준 재검증.

## 세션 정리 (9/28 밤): 필터 baseline 위 재계산 · 지속성 검정 · 시도 수 정리
- vol targeting+RP를 편입일 필터 baseline 위에서 재계산(pit_full.py, pit_vt.py, 4창 434기간, insample target_vol): 필터 없음/있음 모두 Sharpe 개선 근거 없음(dSharpe CI가 0 포함, RP 0%에서는 baseline과 동일 수준). 필터 후 baseline은 avg_net 23.2%, Sharpe 0.0734, mdd -27.2%이고 vt0.7/RP3.35%는 18.6%/0.0730/-19.3%. 낙폭-수익 맞바꿈만 재현
- 성과 지속성(persist.py): 직전 6/12/24기간 평균 수익과 다음 기간 수익의 상관 r=-0.011~-0.050, p 0.21~0.81(전부 p>=0.2). 성과 기반 진입 조정 규칙은 근거 없어 만들지 않음
- 필터 baseline DSR: 시도 보정 없이 0.937(0.95 미달), 보정하면 0.2~0.77. 통계적 근거 약함 = 데이터 부족을 뜻함(알파 부재의 증거가 아님). 5일 주기 약 500기간(약 1년 추가)이 되어야 M=1 기준 문턱을 넘을 수 있으나 실제 값이 관측값보다 낮으면 못 넘을 수 있음
- 장부 20~33번(한서가 별도 요청): 일일 익절 X=2/3/4%, 변동성 상위 일일 단타(top_n 5/10/20), momentum 단독+low_vol, 기존 조합+안정형 알파 모두 NO-GO. 익절·단타는 표본이 1~4개월이라 통계적 결론은 불가
- 시도 수는 거친 합산으로 150~200, 정확한 계수는 미확정
- 다음: 라이브 paper 12번 리밸런싱마다 누적/낙폭/z값 점검(알림 기준, 자동 조정 아님). 1년 쌓이면 z값 재계산. 코인은 저빈도/다중 코인 단면이 새 가설로 남음(별도 결정). 워커 요청은 예산(후보 수)과 사전 기준, 필터(pit_lib.py) 강제, 범위 제한 문구 필수

## 세션 업데이트 (9/28→9/29): KIS 모의투자 매도 TR ID 버그 발견 및 수정, 첫 자동 리밸런싱 성공
- 원인: kis_client.py의 모의투자 매도 TR ID가 "VTTT1006U"(존재하지 않는 값, 실전 TTTT1006U를 잘못 치환한 것으로 추정)였음. KIS 공식 문서(koreainvestment/open-trading-api) 확인 결과 미국 모의투자 매도의 정식 TR ID는 "VTTT1001U"
- 9/28 19:40 UTC 첫 자동 실행: 매도 6건 전부 "모의투자에서는 해당업무가 제공되지 않습니다" 에러, 매수 4건은 예수금 부족으로 skip. last_rebalance.json 미생성(가드 정상 동작)
- TR ID를 VTTT1001U로 수정(kis_client.py.bak_pre_sellfix 백업) 후, 9/29 19:40 UTC 두 번째 자동 실행: 매도 7건(CHTR/INTU/JBHT/MRNA/PLTR/VEEV/WDAY) 전부 성공, 매수 6건(FSLR/GEN/HPE/MGM/MPC/PAYX) 성공, SMCI만 예수금 부족(필요 12,098/보유 11,637)으로 skip
- 신호가 매일 갱신되는 구조라 as_of가 2026-09-25→2026-09-28로 넘어간 채 리밸런싱됨(완전 체결 전까지 목표가 계속 바뀔 수 있음, 며칠 연속 미완료 시 목표가 계속 흔들리는 패턴 주의)
- 결과 계좌: 예수금 $11,315.89, 보유 FSLR 68/GEN 584/HPE 196/MGM 383/MPC 30/MRNA 59/PAYX 121 (SMCI 미체결)
- 다음 확인: 내일 밤 크론이 남은 SMCI를 채우는지, last_rebalance.json이 정상 생성되는지
