# GARUD IMPLEMENTATION LOG

## Session 22 Oct 2026 (audit)

**Baseline:**
- `main` at `27ae2be`.
- 215 tests passed, 0 failed.
- UI smoke test passed.

**Checkpoint:** all changes are in one commit on top of the baseline. The owner uploads them via the GitHub web editor.

| # | Feature IDs | Change | Files | Tests | Result |
|---|---|---|---|---|---|
| 1 | 54, 139 | Weekly backup now runs a **restore drill**. It loads the file just written into a throw-away SQLite DB (built-in `sqlite3`, independent of the app's DB code) and compares row counts, per-event-type counts, unique trade ids and total realised P&L. If they differ, the run fails and Telegram shows "Restore drill FAILED" | `backtest/backup_db.py` | `tests/test_backup_db.py` +2 (good file, damaged file, empty DB) | PASS. Production drill pending (next Sunday 18:00 IST) |
| 2 | 57 | **pip-audit** known-vulnerability report in the Tests run summary. It is report-only (`continue-on-error`), so it can never turn Tests red | `.github/workflows/tests.yml` | Visible on the next Tests run | PENDING first run |
| 3 | 97, 130 | Home shows open P&L **after estimated charges** (buy charges paid + sell charges on exit), on the same basis as closed P&L. The old gross figure is kept | `garud_mobile.py` (`unrealised_net`) | UI smoke test asserts the new line | PASS |
| 4 | 99, 89 | **NSE holiday calendar** (2026, cross-checked with two sources). The Health data-freshness check no longer calls a holiday "data stuck". Trading logic is unchanged | `backtest/nse_calendar.py` (new), `garud_health.py` | `tests/test_nse_calendar.py` (2) | PASS |
| 5 | 59 | App version set to `2026.10.22-A1` | `garud_health.py` | — | PASS |
| 6 | P0 cost finding (Part 4 #26, IDs 28/97) | Real Upstox 2026 delivery charges as an **optional** model: `ChargeModel.dp_per_sell` (default 0, so old results are unchanged) and `upstox_delivery_2026()`. `tax_study.run(..., charges=)`. New one-time study "Cost re-check": old model vs Upstox at ₹3L and ₹1L, plus the extra cost on closed swing paper trades. Event COST_RECHECK; research card | `backtest/backtest_engine.py`, `backtest/tax_study.py`, `backtest/cost_recheck.py` (new), `backtest/run_cost_recheck.py` (new), `.github/workflows/cost_recheck.yml` (new), `garud_research.py` | `tests/test_cost_recheck.py` (4) | PASS. Switching paper P&L needs owner approval |
| 7 | — | Audit reports | `docs/GARUD_*` | — | — |

**After:** 223 tests passed, 0 failed; UI smoke test (10 screens, plus Ask Garud and macro) passed.

**Not changed at that point (needed owner approval):** gap-aware paper stops (ID 14). Approved later the same day (decision B, part 3, row 18).

## Session 22 Oct 2026, part 2 (P2 items; information and safety only, no rule changed)

| # | Feature IDs | Change | Files | Tests | Result |
|---|---|---|---|---|---|
| 8 | 11, 103, 12, 132 | Tests for the Tools modules: Monte Carlo, bootstrap, walk-forward, correlation | `tests/test_tools_modules.py` (new) | 4 | PASS |
| 9 | 20 | M2 robustness bootstrap also reports the chance of a fall deeper than 25% (`p_dd_over_25`). Shown after the next robustness run | `backtest/m2_robustness.py`, `run_m2_robustness.py`, `garud_research.py` | `test_m2_robustness.py` +2 asserts | PASS |
| 10 | 17 | Momentum card: current drawdown % and days below peak | `garud_research.py`, `garud_mobile.py` | `test_momentum_paper.py::test_days_below_peak` | PASS |
| 11 | 72 | `longterm.metrics` adds `longest_dd_days` (peak → recovery) | `backtest/longterm.py` | `test_portfolio15.py::test_longest_drawdown_days` | PASS |
| 12 | 41, 42 | Condor entry records the widest bid-ask spread % (Telegram + Options tab). **Not a filter.** Filtering would change the registered options test, so that needs owner approval | `backtest/options_paper.py`, `garud_mobile.py` | `test_options_paper.py` +1 assert | PASS |
| 13 | 60 | Handbook: restore-from-backup steps | `docs/GARUD_HANDBOOK.md` | — | — |

**After part 2:** 229 tests passed, 0 failed; UI smoke test passed.

## Session 22 Oct 2026, part 3 (owner decision A: real broker charges)

| # | Change | Files | Tests | Result |
|---|---|---|---|---|
| 14 | Paper positions **opened from 23 Oct 2026** are priced with Upstox 2026 delivery charges. `charges_for(entry_day)` is chosen by entry/fill day; older positions keep the old model and are never re-priced | `backtest/backtest_engine.py` (`REAL_COSTS_FROM`, `charges_for`), `backtest/paper_rule.py` (`net_pnl(..., entry_day)`), `backtest/run_momentum_paper.py` | `tests/test_real_costs.py` (3) | PASS |
| 15 | Momentum rebalance charges **one order per symbol**, so the flat ₹20 brokerage is counted once (not per share in the top-up loop). Results under the old percentage-only model are identical | `backtest/momentum_paper.py` | `tests/test_real_costs.py`, `test_momentum_paper.py` | PASS |
| 16 | Benchmark **v3** = FillModel v2 + real charges, stored next to v1/v2 by the "Rule benchmark v2 + v3" workflow. Checkpoints keep v1, so the yardstick is never lowered after seeing results | `backtest/rule_report.py`, `backtest/run_benchmark_v2.py`, `.github/workflows/benchmark_v2.yml`, `garud_mobile.py` (research row) | `tests/test_benchmarks.py` +1 | PASS. Owner must run the workflow once |
| 17 | Home open-P&L estimate uses the entry day's charge model. Ask Garud knows the cost basis and the Cost re-check results (`ask_v3`) | `garud_mobile.py`, `llm/ask_garud.py` | UI smoke test | PASS |

| 18 | **Decision B:** paper stops on a gap-down fill at min(stop, open) for positions opened from 23 Oct 2026 (`GAP_AWARE_FROM`). Older positions keep the stop-price fill; closed trades are never re-priced | `backtest/paper_rule.py` | `tests/test_paper_rule.py::test_gap_down_fill_by_entry_day` | PASS |
| 19 | Benchmark v3 results recorded (v2 rule PF 0.87 under realistic costs) | `docs/GARUD_QUANT_VALIDATION.md`, `llm/ask_garud.py` | — | — |

**After part 3:** 233 tests passed, 0 failed; UI smoke test passed.

## Session 22 Oct 2026, part 4 (owner's second prompt: safety, P&L, recovery, validation)

| # | Items | Change | Files | Tests | Result |
|---|---|---|---|---|---|
| 20 | #25 #115 | Order state machine: each live order's state stored once per change; impossible changes reported; status-call failure → UNKNOWN, retried | `execution/order_state.py` (new), `backtest/live_executor.py` | `tests/test_execution_safety.py` | PASS (fake broker) |
| 21 | #113 | **Bug fixed.** Partly filled then cancelled BUY was treated as "nothing bought" (shares without a stop). Now the stop covers the filled qty; an order still working the next day is cancelled, then protected | same | same | PASS |
| 22 | #117 | **Bug fixed.** GTT stop triggers were off the NSE tick grid and would be rejected. NSE tick bands (15 Apr 2025), round UP, safe near band edges; quantity validation | `risk/pretrade.py` (new) | same | PASS |
| 23 | #47 #118 | Cash/margin check: broker funds read once per run, BUY reduced or blocked (fail closed), running cash across BUYs | `risk/pretrade.py`, `brokers/upstox_live.py` (`get_funds`) | same | PASS (fake broker; Upstox endpoint not called live) |
| 24 | #26 | Position reconciliation after every live run (missing or extra shares reported, never traded) | `execution/position_recon.py` (new) | same | PASS |
| 25 | #97 | Charge tests from the fee schedule. **Options rates updated** for condors from 23 Oct 2026 (STT 0.15%, NSE 0.03553%, exercise STT 0.15%) | `backtest/options_paper.py` | `tests/test_charges.py` (7) | PASS. Not checked against a contract note |
| 26 | #54 #139 #60 | **Full restore drill:** backup restored through Garud's own DB code into a throw-away SQLite file (refuses production), integrity checks plus app readers, then the real Streamlit app started headless | `backtest/restore_drill.py` (new), `.github/workflows/backup_db.yml` | `tests/test_restore_drill.py` (3; the SQLAlchemy test runs on GitHub only) | PASS locally; first production drill on Sunday |
| 27 | #69 #61 #140 | Live-readiness checklist (Health tab) and broker permission audit | `backtest/live_readiness.py` (new), `docs/GARUD_LIVE_READINESS.md` (new), `garud_mobile.py` | `tests/test_live_readiness.py` (2) | PASS |
| 28 | Options PF/1-30 | Per-condor "કેમ?" diagnosis (leg entry → exit, rupee effect) | `backtest/options_paper.py` (`diagnose`), `garud_mobile.py` | `test_options_paper.py::test_diagnose_closed_condor` | PASS |

**After part 4:** 263 tests passed, 0 failed; UI smoke test (all screens incl. Health checklist) passed.

## Session 22 Oct 2026, part 5 (paper replay — first half of the Feb 2027 check, today)

| # | Change | Files | Tests | Result |
|---|---|---|---|---|
| 29 | **Paper replay:** the real momentum paper engine (whole shares, paper capital, Upstox charges, next-close fills, weak-market switch) replayed month by month over the last ~2 years and compared with the backtest engine on the same dates and charges. ENGINE OK = gap ≤ 2 pp/yr and idle cash ≤ 10% (registered before running). Event PAPER_REPLAY; research card; manual workflow | `backtest/paper_replay.py`, `backtest/run_paper_replay.py`, `.github/workflows/paper_replay.yml` (new), `garud_research.py` | `tests/test_paper_replay.py` (3) | PASS on synthetic data. Real run: owner runs the workflow |
| 30 | **Bug fixed (found by the replay):** in `tax_study.simulate_taxed` the 0.2% cash buffer was too small for Upstox's flat ₹20/order, so the last buys of a rebalance were skipped and that money sat in the liquid fund. Percentage-only charges are unaffected (TAX_STUDY results unchanged). **The COST_RECHECK "Upstox" rows of 22 Oct were affected and must be re-run** | `backtest/tax_study.py` | `test_tax_study.py::test_flat_charges_never_leave_a_stock_in_cash` (fails before the fix, passes after) | PASS |

**After part 5:** 267 tests passed, 0 failed.

## Earlier sessions (for traceability)

- **18 Oct:**
  - Live safety hardening (fail-closed limits, order value cap).
  - FillModel v2 and Benchmark v2.
  - Evidence matrix v2.
  - Pinned requirements.
- **19–21 Oct:**
  - Phase 2 portfolio tests.
  - Momentum 200 (M2), M2 robustness, Engine 2 (swing, failed), ML lab (not adopted).
  - Momentum paper portfolios.
  - Sector and drawdown alerts.
  - Weekly backup.
  - Tax study.
- **22 Oct (before audit):**
  - Ask Garud (`llm/ask_garud.py`) and market backdrop card (`backtest/macro.py`).
  - Condor display fixes.
  - Ask Garud fact correction (`ask_v2`).
