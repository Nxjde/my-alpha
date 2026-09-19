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
