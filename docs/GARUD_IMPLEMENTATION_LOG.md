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

**Not changed (needs owner approval):** `GAP_AWARE_STOPS` (ID 14). It would change how future paper exits are priced.

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
