# GARUD QUANT VALIDATION — 22 Oct 2026

**Purpose:** test whether ₹1–3 lakh can beat a 7% bank FD over the long run with controlled risk. This document is **not a profit promise**.

**No strategy is declared profitable.** Backtests are past results only. The paper (forward) tests decide.

## Headline results (reproducible: each study is stored as a versioned event and can be re-run from Actions)

| Strategy | Period | CAGR before tax | After tax (income ≤ ₹12L) | Max drawdown | Status |
|---|---|---|---|---|---|
| FD 7% | 15 years | 7.0% | 7.0% (rebate) | 0% | Benchmark |
| NIFTY ETF buy & hold | 2011-09 → 2026-09 | 11.67% | 10.95% | 36.3% | Benchmark |
| **M2** Momentum 200 + weak-market switch | same | 24.6% | 21.79% | 18.5% | Backtest PASS. **Biased** (today's NIFTY 200 list). Paper from 2 Nov 2026 |
| **G** NIFTY 50 momentum (true list) + switch | same | 11.39% | 10.02% | 17.1% | Backtest PASS. Paper from 2 Nov 2026 |
| Swing v1/v2/v3 (paper rules) | 5-year benchmark, 2021-09 → 2026-09 | **v3 benchmark (realistic fills + Upstox charges, 22 Oct):** v1 PF 1.04 (+₹1,378 / 90 trades) · v2 **PF 0.87 (−₹38,646 / 705 trades)** · v3 PF 1.09 (+₹73,844 / 1,198 trades). v1 legacy figures 1.43 / 1.14 / 1.28 | — | v3 in one account: 35% | Paper: v2 6/30 closed, PF 0.19. **Not proven.** Under realistic costs v2 loses money in backtest |
| Engine 2 swing (dip-buy) | 15 years | −1.8% to +0.9% | — | 35–51% | **FAILED** |
| Intraday ORB | 2 years | PF 0.67 | — | — | **FAILED** (costs) |
| ML picker | 10 years out-of-sample | 13.67% | — | 40% | Not adopted (lost to M2 by more than 2 pp) |
| Options iron condor | Forward only | — | — | 1/30 closed: −₹2,874 | Not proven. No backtest (no free historical options data) |

**Costs (P0 finding, resolved 22 Oct):**
- The rows above use the old model (brokerage ₹0, no DP).
- The Cost re-check with Upstox 2026 charges, after tax (**corrected re-run, 22 Oct**):

| Strategy | ₹3 lakh | ₹1 lakh |
|---|---|---|
| M2 | 21.49% | 20.99% |
| G | 9.72% | 9.06% |
| NIFTY ETF | 10.95% | 11.11% |

- Swing trades cost about ₹71 more each.
- Since 23 Oct 2026, new paper positions pay the real charges.

## Validation checklist (Part 7)

| # | Check | Swing v1–v3 | Options condor | M2 | G |
|---|---|---|---|---|---|
| 1 | Net return after costs | Yes (ChargeModel) | Yes (leg charges) | Yes | Yes |
| 2 | Brokerage, STT, exchange charges, GST, stamp duty, DP | Yes for positions from 23 Oct 2026; benchmark v3 | Yes | Yes (paper from 2 Nov; Cost re-check) | Yes (same) |
| 3 | Realistic slippage | FillModel v2 (benchmark v2) | Bid/ask fills | Charges only | Charges only |
| 4 | Corporate actions / dividends | Adjusted prices (yfinance) | n/a | Adjusted prices + rename/demerger stitching | Same |
| 5 | Look-ahead bias | Completed bars only; tested | n/a | Signal at month-end close, fill next session | Same |
| 6 | Survivorship bias | Today's universe lists | n/a | **Yes: today's NIFTY 200 list (optimistic)** | Point-in-time NIFTY 50 list |
| 7 | Data leakage | — | — | — | ML lab strict no-look-ahead test |
| 8 | Train/test separation | Evidence matrix split 2024-09-27 | Forward only | Last 5 years shown separately | Same |
| 9 | Walk-forward | Tools only (untested) | — | ML lab only | — |
| 10 | Different regimes | Evidence matrix | — | Weak-market switch; yearly table | Same |
| 11 | Trade count / uncertainty | 30-trade checkpoints, z-score | 30 condors | Bootstrap (0% below FD, 5th percentile 16.97%) | — |
| 12 | Max drawdown | Yes | Circuit breaker −₹15,000 | 18.5% | 17.1% |
| 13 | Exposure and concentration | Sector display | 1 lot | Sector line (warn at 40%) | Same |
| 14 | Benchmark comparison | Backtest PF vs paper | FD | NIFTY ETF, NIFTY 200, Momentum 30 ETF | NIFTY ETF |
| 15 | Parameter sensitivity | — | — | 6 variants: 5/6 pass (quarterly fails) | — |
| 16 | Performance decay | Checkpoint z-score | — | NSE Momentum index weaker in the last 5 years (about 9%) | — |
| 17 | Paper vs backtest | Running (6/30) | Running (1/30) | From Nov 2026 | From Nov 2026 |
| 18 | Liquidity constraints | NIFTY 50 / 8 stocks | Bid/ask required | Top 150 by traded value | NIFTY 50 |
| 19 | Gap risk / stop limits | Backtest v2/v3 yes; paper yes for positions opened from 23 Oct 2026 (decision B, `paper_rule.GAP_AWARE_FROM`) | Defined risk | No stops (monthly) | Same |
| 20 | Independent reproduction | Every study re-runnable from Actions; tests on synthetic data | — | M2 base variant reproduced inside the robustness study | — |

## FD comparison

| Aspect | Bank FD | Momentum strategies |
|---|---|---|
| Period | Same 15 years | — |
| Tax | Interest is effectively tax-free for slab A (rebate), using today's rules for all years | Short-term gains 20%; long-term gains 12.5% above ₹1.25L |
| Liquidity | Locked for the term | Can be sold any day, but in a weak market the money sits in a liquid fund |
| Risk | Capital-safe | Drawdowns of 17–19% in backtests; real drawdowns can be larger |

## Options: why "PF 0.0" and "1/30" (22 Oct 2026)

**Why only 1/30 closed:**
- The rule opens at most **one condor per weekly expiry**, on Wed–Fri mornings, 4–10 days before expiry.
- The first condor opened on 21 Oct 2026, so 30 condors take about 7 months, until around May 2027.
- 1/30 is the expected pace, not a fault.

**Why PF 0.0:**
- Profit factor = gross profit of winning condors ÷ gross loss of losing condors.
- The only closed condor (IC-2026-10-27) lost −₹2,874 (STOP_LOSS) and none has won yet, so PF = 0 ÷ 2,874 = 0.
- That is arithmetically correct and says nothing yet about the rule.

**What the stop means:**
- The stop fires when the cost to close is ≥ 2× the credit received.
- The condor was opened and stopped on the same day (21 Oct).
- From the stored numbers: credit ₹2,395 for the lot, net −₹2,874 after charges, so the closing debit was about 2.1× the credit.

**Cause — two candidates, not yet decided:**
- (a) A real NIFTY move towards one short strike.
- (b) Wide bid-ask quotes on the legs. Exits buy back at the ask and sell the wings at the bid, so a wide spread alone can inflate the closing cost.

**How it will be decided:**
- The Options tab now shows a **"કેમ?" card** for every closed condor: each leg's entry → exit price and its rupee effect.
- Every new condor records the widest bid-ask spread at entry.
- If (b) turns out to be the cause, changing the stop to use mid prices would change the registered test. That needs the owner's approval and is **not** done.

## AI ranking / expected return (22 Oct 2026)
- **M2 (rule) is the benchmark.**
- The ML picker (`backtest/ml_lab.py`) is a separate, pre-registered experiment:
  - walk-forward, retrained yearly on past data only;
  - strict no-look-ahead test;
  - acceptance = beat M2 by ≥ 2 percentage points CAGR **and** max drawdown ≤ 25% out-of-sample.
- **Result (21 Oct):** 13.67% / DD 40% vs M2 22.07% / DD 18.5%, so it is **not adopted**.
- The Tools-tab AI score (`scoring/ai_scoring_engine.py`) only explains signals. No automatic paper or live decision uses it: paper trades store `ai_score=0`.

## Evidence still needed (blockers — no fake data used)

| Item | What is missing |
|---|---|
| Swing rule verdicts | 30 closed paper trades per rule (v2 at 6) |
| Options verdict | 30 condors (around May 2027) |
| Momentum paper vs backtest | Monthly fills from 2 Nov 2026; decision Feb 2027 |
| Options backtest | Paid historical option-chain data |
| Charges vs a real contract note | A real order (live is OFF) |

## Paper replay — the real paper engine on the last 2 years (22 Oct 2026)

Period 2024-10-11 → 2026-10-22, with whole shares, paper capital, Upstox charges and fills at the next close.

| Portfolio | Paper | Backtest | Gap | Max fall | Idle cash | Months in liquid fund |
|---|---|---|---|---|---|---|
| M2 ₹3L | 7.84%/yr | 7.84% | 0.0 pp | 10.6% | 1.4% | 14/24 |
| G ₹1L | 1.37% | 0.55% | 0.8 pp | 9.3% | 5.5% | 14/24 |
| M2 ₹1L | 6.68% | 6.05% | 0.6 pp | 10.4% | 5.1% | 14/24 |

- NIFTY ETF over the same period: −3.56%/yr. FD: 7%.
- **Engine OK for all three:** the paper engine reproduces the backtest.
- **Reality check:** in the last 2 years M2 earned about FD-level returns, before tax, mainly by sitting in the liquid fund during the weak market. It did *not* earn the 15-year average of about 21%.
- G earned less than FD.
- Expect long FD-like or worse stretches.
