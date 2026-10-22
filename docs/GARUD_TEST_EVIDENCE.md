# GARUD TEST EVIDENCE — 22 Oct 2026

## How tests were run

- **Local (this audit):** the repository's pytest suite, run under a small pytest-compatible runner.
  - The workspace cannot install from PyPI.
  - It loads `tests/conftest.py`, which blocks all market-data downloads.
  - The database and brokers are fakes; there is no network and no secrets.
- **GitHub:** the "Tests" workflow runs the same suite with real `pytest` on every upload. The owner has sent green results for earlier uploads.
- **UI smoke test (local):** imports `garud_mobile.py` with a stub Streamlit and fake database, then renders all 10 screens. It asserts on key numbers and texts, including Ask Garud (answer saved as ASK_GARUD; prompt contains real positions) and the macro card.

## Results

| Run | Passed | Failed |
|---|---|---|
| Baseline 27ae2be | 215 | 0 |
| After audit changes | 223 | 0 |
| After part 2 (P2 items) | 229 | 0 |
| After part 3 (real charges) | **233** | **0** |
| UI smoke test, after | 10/10 screens | 0 |

**Per file** (number of test functions; parametrised cases make the total 233):

| File | Tests | File | Tests |
|---|---|---|---|
| test_app_status | 5 | test_momentum_paper | 17 |
| test_ask_garud | 6 | test_nse_calendar (new) | 2 |
| test_backtest_fills | 10 | test_options_paper | 8 |
| test_backup_db | 3 (+2 new) | test_paper_rule | 11 |
| test_benchmarks | 3 | test_portfolio15 | 8 |
| test_check_tokens | 2 | test_repo_hygiene | 3 |
| test_cost_recheck (new) | 4 | test_tools_modules (new) | 4 |
| test_real_costs (new) | 3 | | |
| test_live_executor | 11 | test_sandbox_mirror | 4 |
| test_live_gates | 19 | test_scanner | 1 |
| test_live_guard | 9 | test_swing2 | 5 |
| test_m2_robustness | 4 | test_tax_study | 7 |
| test_macro | 4 | test_trading_mode | 5 |
| test_ml_lab | 4 (incl. strict no-look-ahead) | test_momentum200 | 7 |

## Production evidence (real outputs received by the owner)

| Date | Evidence |
|---|---|
| 18 Oct | Benchmark v2: v2 PF 1.04, v3 PF 1.20 (FillModel v2) |
| 18 Oct | Evidence matrix v2: no proof that regime selection helps |
| 19 Oct | Weekly backup: 20 trades, 170 events |
| 21 Oct | Manual pipeline run: all checks OK |
| 21 Oct | Momentum dry run: two passes, 20 and 10 stocks |
| 21 Oct | M2 robustness: 5/6 variants pass |
| 21 Oct | ML lab: ML not adopted |
| 21 Oct 21:22 | Tax study: M2 21.79% and G 10.02% after tax; NIFTY ETF 10.95%; FD 7% |
| 21 Oct 21:30 | App screenshot: data 21 Oct, run 1 hour ago, v2 6/30 closed (−₹4,064), condor 1/30 (−₹2,874) |
| 22 Oct ~13:00 | Cost re-check: M2 21.18% / G 9.74% / ETF 10.95% after tax with Upstox charges at ₹3L; ₹71 extra per swing trade |
| 22 Oct 10:20 | Ask Garud answered from real data. One wrong fact was found and corrected (`ask_v2`) |

## Known failures found and fixed this month

- **21 Oct:** a stray line in `run_momentum_paper.main()` made every scheduled run exit with code 1. Fixed, and a `main()` regression test was added.
- **22 Oct:** Ask Garud standing facts were misleading about regime switching. Corrected.

## Not verified here

| Item | Why | How to verify |
|---|---|---|
| Live DB row counts and stored benchmark values | No DB access | Owner opens the Research / Trades tabs |
| pip-audit output | Runs on GitHub only | Tests run summary |
| Restore drill on the real backup | Runs on GitHub only | Telegram "Restore drill OK" on Sunday |
| Macro card with real Yahoo data | Network blocked here | Owner checks the Mode tab |
