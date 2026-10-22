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
- The Cost re-check with Upstox 2026 charges, after tax:

| Strategy | ₹3 lakh | ₹1 lakh |
|---|---|---|
| M2 | 21.18% | 20.79% |
| G | 9.74% | 9.10% |
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
