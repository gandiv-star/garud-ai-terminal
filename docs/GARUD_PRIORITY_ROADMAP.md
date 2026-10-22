# GARUD PRIORITY ROADMAP — 22 Oct 2026

How priorities were scored:
- **First:** capital protection, data correctness and trading correctness.
- **Then:** usefulness at ₹1–3 lakh capital, regression risk and testability.

Being AI/ML does not raise a feature's priority. An "AI feature" that lost to a simple rule in Garud's own tests (ML picker, 21 Oct) stays P3.

## P0 — Critical

| Item | Status |
|---|---|
| **Cost model understates broker charges.** Every backtest and paper P&L assumes brokerage ₹0 and no DP charge. Upstox 2026: ₹20 per order, plus ₹20 + GST DP per scrip sold (about ₹71 extra per swing round trip) | Measurement ready: Actions → "Cost re-check (Upstox 2026 charges)". **Owner approval needed** to make `upstox_delivery_2026()` the model for new paper trades and a new benchmark version. Old results are kept, not rewritten |

Live trading is OFF, so the execution items below are P3 today. They **become P0 on the day live trading is considered**:

| ID | Item | Why it becomes P0 |
|---|---|---|
| 25 | Persisted order state machine | Every live order needs exactly one known state |
| 26 | Daily live position reconciliation | Broker positions must match internal records |
| 30 | Emergency flatten workflow | Need to exit everything in one action |
| 47/118 | Margin and cash check before orders | Avoid rejections and over-commitment |
| 61/62/70 | Broker permission audit and SEBI/NSE checklist re-verification | Rules changed in 2025–26 |
| 113/117 | Partial fill, cancel/replace and tick-size handling for limit orders | Correct fills |

## P1 — High

| ID | Item | Status after this session |
|---|---|---|
| 54/139 | Backup restore drill | **DONE in code**. Verified by tests; first production drill on the next Sunday run |
| 57 | Dependency vulnerability report | **DONE** (report-only step in the Tests workflow) |
| 97/130 | Open P&L after charges | **DONE** |
| 99 | NSE holiday calendar for health checks | **DONE** (2026 list; add 2027 when NSE publishes it) |
| 2 | Momentum paper test (M2 ₹3L, G ₹1L) | Running automatically. First fill 2 Nov 2026; decision Feb 2027 |
| 14 | Gap-aware paper stops | **Needs owner approval.** It changes how future paper exits are priced. It is more honest; already-closed trades stay unchanged |
| 10 | Promotion gate | Stays manual by design: the owner decides after PASS |

## P2 — Medium (next sessions, in order)

**Done 22 Oct (part 2):**
- (11/12/103/132) tests for the Tools modules.
- (17/72) drawdown days.
- (20) bootstrap chance of a fall > 25%.
- (41/42) spread recorded at entry. A spread *filter* needs owner approval.
- (60) restore steps.

Still open:

1. **(8) Momentum decay check.** After 3 rebalances, compare paper monthly returns with the backtest distribution.
2. **(28/96) Slippage report.** Compare sandbox fill prices with paper entries.
3. **(41/42) Options chain checks.**
   - Skip quotes older than 5 minutes.
   - Skip entry if any leg's bid-ask spread is above 20% of mid.
   - Both change the registered options test, so they need owner approval. Spreads are already recorded.
4. **(51/53) Price cross-check.**
   - Compare yfinance with Upstox for open positions.
   - Flag possible splits (more than 40% overnight move).
5. **(35) Results calendar filter.** BLOCKED until a reliable free source is found.

## P3 — Later or not planned

These are not planned, or wait for proof:

| IDs | Item | Reason |
|---|---|---|
| 21, 22, 24 | Partial booking, trailing SL, failed-breakout exit | The swing rules they would modify failed 15-year tests |
| 39, 34 | Intraday and multi-timeframe | INTRADAY_TEST: costs exceed edge |
| 5–7, 107–109 | Expected-return, calibration, drift monitoring | Only after an ML model beats M2 (it did not) |
| 16, 19, 94 | Allocation optimizer, cash forecast, stress scenarios | Revisit after the momentum and options paper results |
| 48, 50, 63 | Live options execution, options backtest, broker rate controls | BLOCKED: live access or paid data needed |

## Dependency order

```
Momentum paper (Nov–Feb) ──> decay check (P2-1) ──> owner decision (Feb 2027)
                                                       │
                                     if small real money: manual orders from the Telegram list
                                                       │
                       if automatic live ever: P0-before-live list above + static IP + daily token
```
