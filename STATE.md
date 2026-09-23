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
