# GARUD MASTER AUDIT — 22 Oct 2026

**Baseline:** repo `gandiv-star/garud-ai-terminal`, branch `main`, commit `27ae2be` (22 Oct 2026 10:23 IST).
This audit's changes were committed separately as a checkpoint on top of it.
**Auditor:** Claude, working in a cloud workspace. It has read-only access to GitHub, no database credentials and no broker credentials.
**Evidence used:**
- Source code.
- The local test run (fake database and brokers; no network).
- Results the owner received from production runs (Telegram messages and screenshots) during October 2026.

Anything that needs the live database or secrets is marked UNVERIFIED or BLOCKED.

**Where the reports are:** the 10 reports live directly in `docs/` (not `docs/audit/`), so the owner can upload them from a phone into an existing folder:
- `GARUD_MASTER_AUDIT.md`, `GARUD_FEATURE_INVENTORY.csv`, `GARUD_PRIORITY_ROADMAP.md`
- `GARUD_IMPLEMENTATION_LOG.md`, `GARUD_TEST_EVIDENCE.md`, `GARUD_SECURITY_AUDIT.md`
- `GARUD_QUANT_VALIDATION.md`, `GARUD_SYSTEM_ARCHITECTURE.md`, `GARUD_DEPENDENCIES_AND_BLOCKERS.md`, `GARUD_NEXT_SESSION_HANDOFF.md`

## સારાંશ (ગુજરાતી)

- **Features ચકાસ્યા:** 140 માંથી 140, ઉપરાંત app ના 28 દાવા.
- **દરેકનો હાલનો દરજ્જો (audit પછી):**

| દરજ્જો | સંખ્યા |
|---|---|
| WORKING_VERIFIED | 56 |
| PARTIAL | 56 |
| NOT_IMPLEMENTED | 23 |
| BLOCKED | 3 |
| CODE_ONLY | 2 |
| UNVERIFIED / FAILED | 0 |

- **P0 (ગંભીર) ખામી: 1 મળી — ખર્ચનો નમૂનો (cost model) ઓછો ખર્ચ ગણે છે.**
  - Garud ના બધા backtests અને paper P&L brokerage ₹0 અને DP charge ₹0 માનીને ગણાયા છે.
  - Upstox ના 22 ઓક્ટોના સત્તાવાર દર: delivery માં દરેક order પર ₹20 brokerage, અને દરેક વેચાણ પર ₹20 + GST DP charge.
  - અસર: દરેક swing trade પર આશરે ₹71 વધુ ખર્ચ થાય. Momentum પર પણ અસર છે; નાની રકમ (₹1 લાખ) પર વધુ.
  - **શું કર્યું:** સાચા દરનો નમૂનો (`upstox_delivery_2026`) અને "Cost re-check" અભ્યાસ તૈયાર કર્યા. પરિણામ (22 ઓક્ટો): tax અને સાચા ખર્ચ પછી M2 21.18% અને G 9.74% (₹3 લાખ).
  - **✅ ઉકેલાયું (તમારી મંજૂરી, નિર્ણય A, 22 ઓક્ટો):** 23 ઓક્ટોથી ખુલતા paper trades સાચા ખર્ચે ગણાય છે. નવું benchmark v3 પણ ઉમેર્યું. જૂનાં પરિણામો એમ જ છે.
- **બાકીની P0 ચકાસણીઓમાં કોઈ ખામી નથી** (પુરાવા વિભાગ 3 માં):
  - live trading બંધ છે અને તેના દરેક દરવાજાના tests છે;
  - એક જ trade બે વાર બનતો નથી;
  - કોઈ secret repo માં નથી;
  - જૂના ભાવ પર નવો trade ખૂલતો નથી.
- **P1 માં સુધારેલાં કામ (આ session):**
  1. Database backup ની "restore drill": backup file ફરી લોડ કરીને ગણતરી મેળવવામાં આવે છે.
  2. Dependencies માં જાણીતી security ખામીઓનો અહેવાલ (pip-audit).
  3. ખુલ્લા trades નો નફો/નુકસાન charges બાદ કરીને પણ બતાવાય છે.
  4. NSE રજાઓનું કૅલેન્ડર, જેથી રજાના દિવસે "ડેટા અટક્યો" એવી ખોટી ચેતવણી ન આવે.
- **ઈરાદાપૂર્વક નથી બનાવ્યા:** trailing SL, partial booking, intraday, basket orders, ML model monitoring.
  - કારણ: 15 વર્ષના tests માં swing અને intraday નિષ્ફળ ગયાં, અને ML એ M2 નિયમ કરતાં ખરાબ પરિણામ આપ્યું.
  - આ features ઉમેરવાથી નફો નહીં વધે; માત્ર જટિલતા વધશે.
- **Live trading પહેલાં ફરજિયાત (અત્યારે P3, live ના દિવસે P0):** static IP, order state table, emergency flatten, margin check, compliance ફરી ચકાસણી.
- **નફાકારક જાહેર કરેલી strategy:** એક પણ નહીં.
  - M2 અને G backtest માં tax પછી પણ FD થી આગળ છે, પણ paper test 2 નવેમ્બર 2026 થી શરૂ થશે.

## 1. Baseline

| Item | Result |
|---|---|
| Commit | 27ae2be (main), clean working tree, in sync with GitHub |
| Python files | 142 files at baseline (144 after this audit), about 15,000 lines |
| Tests before this audit | 215 passed, 0 failed (local runner; GitHub "Tests" workflow green per owner) |
| Tests after this audit | 233 passed, 0 failed, plus the UI smoke test of all 10 screens passed |
| Workflows | 16. Rule/momentum/options paper (6 cron times plus a cron-job.org dispatch), Tests, weekly backup, one-time studies, dry run |
| Database | Neon Postgres: tables `trades` and `audit_events`. Last known size 20 trades / 170 events (backup on 19 Oct) |
| Live trading | OFF. TRADING_MODE=PAPER; no LIVE_* variables set (per handbook and the owner) |

## 2. Existing app features (Part 4)

| # | Claimed feature | Status | Evidence / note |
|---|---|---|---|
| 1 | Streamlit Home | WORKING_VERIFIED | `garud_mobile.home`; owner screenshot 21 Oct 21:30 |
| 2 | Regime Engine | WORKING_VERIFIED | `backtest_engine._regime_at`, `trading_mode.decide`; tests/test_trading_mode.py |
| 3 | Smart Scanner | WORKING_VERIFIED | `backtest/scanner.py` SCAN_SNAPSHOT; tests/test_scanner.py |
| 4 | Candlestick chart | WORKING_VERIFIED | `garud_chart.py`; UI test (Plotly candlestick plus stop/entry lines) |
| 5 | Open/Closed trades | WORKING_VERIFIED | Trades tab; owner screenshot |
| 6 | Paper trading | WORKING_VERIFIED | `paper_rule.run_all`; 6 runs per day; v2 6/30 closed (owner screenshot 21 Oct) |
| 7 | Upstox sandbox | WORKING_VERIFIED | `sandbox_mirror.py`; Telegram 🧪 messages; tests/test_sandbox_mirror.py |
| 8 | Live trading OFF | WORKING_VERIFIED | tests/test_live_gates.py (19 test functions, more cases with parameters) |
| 9 | Risk Center | WORKING_VERIFIED | `garud_mobile.risk_page`, `garud_risk.py`; UI test |
| 10 | Sector exposure | PARTIAL | Shown for paper positions and momentum. Only live has an enforced limit |
| 11 | Kill switch | WORKING_VERIFIED | GARUD_KILL_SWITCH; tests |
| 12 | Options iron condor | WORKING_VERIFIED (paper) | 1 condor closed, STOP_LOSS −₹2,874 (owner screenshot) |
| 13 | Research Lab | WORKING_VERIFIED | Study cards; tax study card seen 21 Oct |
| 14 | Strategy registry | WORKING_VERIFIED | `strategies/registry.py`, 8 strategies |
| 15 | Five-year backtests | WORKING_VERIFIED | RULE_BENCHMARK v1 and v2 events (run 18 Oct) |
| 16 | Walk-forward tools | PARTIAL | `backtest/walk_forward.py` (Tools) has no tests; ML lab walk-forward is tested |
| 17 | Slippage stress | WORKING_VERIFIED | FillModel v2 (benchmark v2); tests/test_backtest_fills.py |
| 18 | Monte Carlo | PARTIAL | Bootstrap in M2 robustness is tested and run. `monte_carlo.py` (Tools) is untested |
| 19 | Neon PostgreSQL | WORKING_VERIFIED | Weekly backup counts; Health DB check |
| 20 | Scheduled runs | WORKING_VERIFIED | Health "Runs: 1 કલાક પહેલાં" (21 Oct). The claim "12 hours old" is **false** |
| 21 | Telegram alerts | WORKING_VERIFIED | Messages pasted by the owner |
| 22 | Gemini | WORKING_VERIFIED | Ask Garud answer, 22 Oct 10:20 |
| 23 | Market data freshness | WORKING_VERIFIED | Health check; now aware of NSE holidays |
| 24 | System health dashboard | WORKING_VERIFIED | Health tab |
| 25 | Broker sandbox validation | WORKING_VERIFIED | Sandbox reconciliation with expected orders |
| 26 | Cost model | **WORKING_VERIFIED (P0 finding fixed 22 Oct)** | `ChargeModel` includes STT, exchange charges, GST and stamp duty (tests/test_paper_rule.py::test_net_pnl_includes_charges). It assumes **brokerage ₹0 and no DP charge**, but Upstox charges ₹20/order and ₹20+GST DP per sell (upstox.com/brokerage-charges, 22 Oct 2026). Owner approved decision A (22 Oct): positions opened from 23 Oct 2026 are priced with `upstox_delivery_2026()` (`backtest_engine.charges_for`). Benchmark v3 added; older trades and results are unchanged |
| 27 | NIFTY/benchmark comparison | WORKING_VERIFIED | Every long-term study includes NIFTY ETF and FD |
| 28 | DB and scheduler reliability | PARTIAL | Concurrency group, idempotent ids and catch-up logic all work. Backup restore drill runs in production from the next Sunday |

### Claimed numbers

These numbers came from old screenshots or reports. None of them is today's live state.

- **v1 PF 1.43 / v2 PF 1.14 / v3 PF 1.28:**
  - These are the **5-year backtest benchmarks, version 1** (legacy fills). They are stored in the DB and shown in the app.
  - With realistic fills (FillModel v2, 18 Oct) the figures are lower: v2 **1.04** and v3 **1.20**.
  - Not re-read from the DB here (no DB access): UNVERIFIED-today.
- **Paper (owner screenshot 21 Oct 21:30):**
  - v1: 1/30 closed, +₹187.
  - v2: 6/30 closed, −₹4,064, PF 0.19.
  - v3: 0/30 closed.
  - These paper figures differ from the backtest PFs above. Samples are far too small to judge before 30 trades.
- **"Options PF 0.0, 1/30":**
  - The 1/30 is correct.
  - With no winning condor yet, PF = 0 gross profit ÷ loss = 0 (correct arithmetic). The Options tab shows "—".
- **"Upstox sandbox 27/27":** shown on the Trades tab from SANDBOX_ORDER events. Not re-counted here (no DB access): UNVERIFIED-today.
- **"Runs 12 hours old":** **false**. The owner screenshot shows "1 કલાક પહેલાં".
- **Open vs closed P&L:**
  - Open P&L = (last close − entry) × qty, **before** charges.
  - Closed P&L is **after** charges.
  - Since this audit, Home also shows the open figure after estimated charges.

## 3. P0 checks

| Area | Check | Result |
|---|---|---|
| Security | Secret-pattern scan of the repo; only the rule workflow can see LIVE_* settings | PASS (tests/test_repo_hygiene.py) |
| Live isolation | Any closed gate → no broker call; invalid limit → BUY refused | PASS (tests/test_live_gates.py) |
| Duplicate orders | internal_order_id is the DB primary key; rule_already_used; options one-per-expiry; workflow concurrency | PASS |
| Stale data | Entry needs today's bar; stock date must equal NIFTY date; momentum refuses prices more than 6 days old | PASS |
| P&L correctness | Closed P&L includes STT, exchange charges, GST and stamp duty. Open P&L was gross (now labelled, with a net estimate added) | PASS after fix |
| **Cost model vs broker** | **Brokerage ₹0 and no DP charge assumed; Upstox 2026 = ₹20/order + ₹20+GST DP per sell (about ₹71 extra per swing round trip)** | **P0 FINDING → RESOLVED.** Owner approved decision A on 22 Oct; positions opened from 23 Oct 2026 use real charges |
| Database corruption | Weekly backup; no restore test existed | FIXED (restore drill) |
| AI authority | AI modules never import brokers; prompts forbid decisions | PASS |

## 4. Master index — all 140 features

Full details for every row (evidence, limitation, plan, acceptance, tests, effort) are in `docs/GARUD_FEATURE_INVENTORY.csv`.

Abbreviations: W = WORKING_VERIFIED, P = PARTIAL, C = CODE_ONLY, N = NOT_IMPLEMENTED, B = BLOCKED.

### A. AI & quant research

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 1 | AI Stock Ranking | P | P3 | scoring/ai_scoring_engine.py AIScoringEngine (0-100 vote score, Tools tab); backtest/momentum200.py ranking… |
| 2 | Momentum Engine | W | P1 | backtest/momentum200.py select(), momentum_paper.py rebalance(), run_momentum_paper.py (stale guard STALE_D… |
| 3 | Regime-aware Strategy Selection | W | P3 | backtest/trading_mode.py decide() mode_v1; TRADING_MODE events; tests/test_trading_mode.py |
| 4 | Adaptive Position Sizing | W | P3 | backtest/paper_rule.py position_size(): 1% risk per trade on ATR stop; backtest/live_guard.py reduces BUY t… |
| 5 | Expected Return Estimation | P | P3 | backtest/ml_lab.py predicts next-month return (research only) |
| 6 | Probability Calibration | N | P3 | No calibration code |
| 7 | Feature Importance / Model Explainability | N | P3 | ml_lab.py does not report importances; llm/explainability.py explains rule decisions only |
| 8 | Strategy Decay Detector | P | P2 | backtest/rule_report.py checkpoint_status() z-score vs benchmark at 10/20/30 trades; analytics/strategy_hea… |
| 9 | Automated Experiment Tracker | P | P2 | Every study stores a versioned audit event (RULE_BENCHMARK v2, EVIDENCE_MATRIX v2, PORTFOLIO_15Y, MOMENTUM_… |
| 10 | Strategy Promotion Gate | P | P1 | Pre-registered PASS rules (rule_report.PF_PASS, options_paper verdict, m2.verdict); live requires TRADING_M… |

### B. Portfolio & capital risk

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 11 | Monte Carlo Simulation | P → W | P2 | backtest/m2_robustness.py bootstrap() 5,000 resamples (run 21 Oct: 0% below FD); backtest/monte_carlo.py + … |
| 12 | Portfolio Correlation Heatmap | P | P2 | portfolio/correlation_engine.py used in Tools portfolio pick (max 0.8) / 22 Oct (2): CorrelationEngine math… |
| 13 | Risk Contribution Analysis | N | P3 | - |
| 14 | Gap Risk Simulator | P → W | P1 | backtest/backtest_engine.py FillModel v2 gap-down stop fill min(stop, open)-0.10%; paper: gap-aware from… |
| 15 | Liquidity and Capacity Model | P | P3 | momentum200: universe = 150 most liquid by 6-month traded value |
| 16 | Capital Allocation Optimizer | N | P3 | backtest/portfolio15.py compares fixed allocations only |
| 17 | Drawdown Recovery Monitor | P → W | P2 | garud_risk.drawdown(); run_momentum_paper DRAWDOWN_ALERT_PCT=15 Telegram alert / 22 Oct (2): momentum card … |
| 18 | Strategy-wise Risk Budget | W | P3 | paper_rule Rule.capital per rule, risk_pct 1%; garud_risk.CAPITAL_PER_RULE; options circuit breaker -Rs.15,000 |
| 19 | Cash and Exposure Forecast | N | P3 | - |
| 20 | Ruin Risk Analysis | P | P3 | m2_robustness bootstrap p_below_fd and 5th percentile / 22 Oct (2): m2_robustness.bootstrap now reports p_d… |

### C. Trading & execution

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 21 | Partial Profit Booking | N | P3 | - |
| 22 | Trailing Stop-loss | C | P3 | risk/exit_engine.py ExitEngine (not wired into paper rules, no tests) |
| 23 | Time-based Exit | W | - | paper_rule.rule_exit() TIME_BASED, time_exit_due_today() |
| 24 | Failed Breakout Exit | N | P3 | - |
| 25 | Order State Machine | P | P2 (P0 before live) | brokers/base_broker.py OrderStatus; live_executor handles PENDING/OPEN/PARTIALLY_FILLED/REJECTED; sandbox_m… |
| 26 | Broker Position Reconciliation | P | P2 (P0 before live) | backtest/sandbox_mirror.py reconcile expected vs mirrored; live_executor.held_quantity(); execution/reconci… |
| 27 | Duplicate Order / Idempotency Protection | W | - | Deterministic internal_order_id (rule-symbol-signal_date) as DB primary key (database/db.py); rule_already_… |
| 28 | Execution Quality and Slippage Report | P | P2 | FillModel v2 slippage (+0.05% entry, -0.05% exit); ChargeModel. P0 FINDING 22 Oct: ChargeModel assumes brok… |
| 29 | Safe Retry Logic | P | P2 | llm/advisor.advise() retries transient errors; pipeline re-runs pick up missed work (momentum due_month_end… |
| 30 | Emergency Exit / Flatten Workflow | N | P2 (P0 before live) | Kill switch blocks new BUYs only (safety/kill_switch.py, GARUD_KILL_SWITCH) |

### D. Market intelligence

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 31 | Relative Strength Heatmap | P | P3 | strategies/relative_strength.py; sector/sector_analysis.py rank_sectors() (Tools) |
| 32 | Sector Rotation Detector | P | P3 | sector/sector_analysis.py; backtest/sectors.py concentration() for momentum |
| 33 | Volume Anomaly Detector | P | P3 | Scanner rel_volume per stock (backtest/scanner.py); strategies/volume_breakout.py |
| 34 | Gap-up / Gap-down Scanner | N | P3 | - |
| 35 | Earnings and Corporate Events Risk Filter | N | P2 | - |
| 36 | Market Breadth Dashboard | P | P2 | backtest/macro.py breadth() + Mode tab card (added 22 Oct) |
| 37 | Volatility Forecast | P | P3 | trading_mode.context() vol20 percentile; India VIX in macro card |
| 38 | Liquidity Scanner | P | P3 | momentum universe by traded value |
| 39 | Multi-timeframe Confirmation | N | P3 | 60-minute bars used only to rebuild missing daily bars (paper_rule._fill_recent_gaps) |
| 40 | News and Event Risk Filter | C | P3 | llm/news_engine.py NewsEngine (Tools, untested) |

### E. Options risk

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 41 | Option Chain Data Validation | P | P2 | options_paper.quotes()/price_legs(): all four legs need live bid and ask; lot size from contracts / 22 Oct … |
| 42 | Bid-Ask Spread and Liquidity Filter | P | P2 | Fills at bid/ask (pessimistic) / 22 Oct (2): spread recorded, NOT used as a filter (a filter would change t… |
| 43 | Implied Volatility and IV Rank | N | P3 | Delta from chain greeks used for strike choice; IV not stored |
| 44 | Greeks Dashboard | P | P3 | delta read per leg (options_paper._md) |
| 45 | Expiry-day Risk Controls | W | - | options_paper.exit_decision EXPIRY_CLOSE from 14:30; settlement at intrinsic |
| 46 | Defined-risk Position Sizing | W | - | Iron condor (always hedged), 1 lot, max loss in entry message; circuit breaker -Rs.15,000 |
| 47 | Maximum Loss and Margin Validation | P | P3 (P0 before live) | Max loss computed; margin not checked (paper) |
| 48 | Multi-leg Execution and Partial-fill Protection | B | P3 | Paper only; no live options code |
| 49 | Expiry / Settlement Risk Checks | W | - | options_paper.settlement(), SETTLED when runs missed |
| 50 | Realistic Options Backtest | B | P3 | Research card: 'Backtest NOT TESTED (no free historical options data)' |

### F. Data & reliability

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 51 | Multi-source Data Validation | P | P2 | paper_rule.scan(): stock last bar must equal NIFTY date; _fill_recent_gaps from 60m bars; longterm._despike() |
| 52 | Historical Data Versioning | N | P3 | - |
| 53 | Corporate Action Adjustments | P | P2 | yfinance adjusted history; nifty50_history.stitch() for renames/demergers |
| 54 | Database Backup and Restore Verification | P | P1 | backtest/backup_db.py weekly artifact (verified: 20 trades / 170 events, 19 Oct). NEW: restore_drill() load… |
| 55 | API Rate-limit Manager | N | P3 | - |
| 56 | Secure Secret Management | W | - | Secrets only in GitHub/Streamlit secrets; tests/test_repo_hygiene.py scans for token patterns; only rule wo… |
| 57 | Dependency and Vulnerability Checks | N → P | P1 | NEW: pip-audit report step in .github/workflows/tests.yml (report only) |
| 58 | CI/CD Quality Gates | W | - | .github/workflows/tests.yml: compileall + pytest on every push (green screenshots from owner) |
| 59 | App Version and Run Reproducibility | P | P3 | garud_health.APP_VERSION (bumped to 2026.10.22-A1); study events carry version + registered date |
| 60 | Disaster Recovery Plan | P | P2 | docs/GARUD_HANDBOOK.md section 6; weekly backup / 22 Oct (2): restore-from-backup steps added to docs/GARUD… |

### G. Compliance & safety

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 61 | Broker API Permission Audit | N | P3 (P0 before live) | - |
| 62 | SEBI/NSE Retail Algo Compliance Checklist | P | P3 (P0 before live) | docs/COMPLIANCE.md (researched Sep 2026) |
| 63 | Broker Order-rate and API Controls | B | P3 | Live off; order volume tiny (<10 OPS) |
| 64 | Live Trading Permission Gates | W | - | brokers/upstox_live.live_orders_allowed(), live_executor gates, live_guard fail-closed limits |
| 65 | Complete Audit Trail | W | - | audit_events table: RULE_ENTRY/EXIT, SANDBOX_ORDER, OPT_*, MOM_*, PIPELINE_RUN, AI_ADVICE, ASK_GARUD, studies |
| 66 | Manual Kill Switch | W | - | GARUD_KILL_SWITCH variable -> allow_entries False; safety/kill_switch.py |
| 67 | Credential Rotation and Access Control | P | P2 | backtest/check_tokens.py expiry warnings 5 days ahead (Telegram, Health) |
| 68 | Paper/Sandbox/Live Isolation | W | - | Separate brokers (upstox_sandbox vs upstox_live), TRADING_MODE, sandbox mirror never places live orders |
| 69 | Live-readiness Verification Checklist | P | P3 | docs/COMPLIANCE.md; handbook section 5 (static IP, daily token, PASS) |
| 70 | Regulatory and Broker-rule Review Process | N | P3 | - |

### H. Performance measurement

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 71 | Net CAGR and Annualized Return | W | - | longterm.metrics(); tax_study after-tax CAGR (TAX_STUDY 21 Oct) |
| 72 | Maximum Drawdown and Drawdown Duration | P → W | P2 | max_dd everywhere / 22 Oct (2): longterm.metrics() longest_dd_days (peak -> recovery); tests/test_portfolio… |
| 73 | Sharpe, Sortino and Calmar | W | - | m2_robustness.sharpe_sortino(); longterm.metrics ratio = CAGR/DD |
| 74 | Win Rate, Average Win and Average Loss | W | - | rule_report._summary(), garud_research.rule_rows() |
| 75 | Profit Factor and Expectancy | W | - | rule_summary pf, avg per trade |
| 76 | Exposure-adjusted Return | N | P3 | - |
| 77 | Benchmark Comparison (NIFTY, ETF, FD) | W | - | Every long-term study includes NIFTY ETF (NIFTYBEES) and FD 7%; momentum card shows NIFTY over same period |
| 78 | Strategy-wise and Regime-wise Performance | W | - | backtest/evidence_matrix.py (EVIDENCE_MATRIX v2) |
| 79 | Paper-versus-Backtest Gap | W | - | rule_report.checkpoint_status() z-score warning at Z_WARN=-2 |
| 80 | Monthly/Quarterly Attribution | P | P3 | longterm.yearly() yearly returns |

### I. Ask Garud & UX

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 81 | Ask Garud AI with real database context | W | - | llm/ask_garud.py + garud_mobile.ask_page(); owner screenshot 22 Oct 10:20; ASK_GARUD events |
| 82 | Gujarati and English Trade Explanation | W | - | llm/advisor.py (AI_ADVICE, Scanner 'AI સમજૂતી') |
| 83 | Why was this trade selected? | W | - | Scanner rows: reason + rule checks + reference stop/qty (backtest/scanner.py) |
| 84 | Why was this trade blocked? | W | - | Scanner WATCH/NO TRADE reasons; Mode tab rejected rules with reason |
| 85 | Natural-language Research Queries | P | P3 | Ask Garud receives study summaries |
| 86 | Telegram Alerts with signal, risk and rationale | P | P3 | Entries show price/stop/qty; momentum shows buy/sell/sector; options show credit and max loss |
| 87 | Daily/Weekly Performance Summary | W | - | Daily Telegram run messages; rule_report.weekly_report(); weekly backup message |
| 88 | Strategy Comparison Reports | W | - | 🔬 Research tab study cards |
| 89 | Data Freshness and Model Confidence Warnings | W | - | garud_health checks (now NSE-holiday aware), momentum stale guard, scanner DATA ISSUE |
| 90 | AI Approval Layer separated from Live Order Authority | W | - | advisor/ask_garud never call brokers; prompts forbid decisions |

### J. Professional features

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 91 | Dynamic Portfolio Exposure Limits | P | P3 | live_guard LIVE_CAPITAL/LIVE_MAX_OPEN/LIVE_MAX_STOCK_PCT (live only) |
| 92 | Regime-specific Drawdown Controls | P | P3 | Momentum weak-market switch; options circuit breaker |
| 93 | Sector and Single-stock Concentration Limits | P | P3 | live_guard max stock %; momentum sector line SECTOR_WARN_PCT=40; Risk tab sector exposure |
| 94 | Portfolio Stress Scenarios | N | P3 | - |
| 95 | Trade Journal and Decision Snapshot | W | - | RULE_ENTRY payload (signal date, regime, stop, qty); SCAN_SNAPSHOT daily |
| 96 | Signal-to-order-to-fill Traceability | P | P2 | internal_order_id -> SANDBOX_ORDER(internal_order_id) -> broker order id |
| 97 | Realized/Unrealized P&L Reconciliation | P → W | P1 | Closed P&L net of charges (paper_rule.net_pnl). NEW: home shows open P&L after estimated charges (garud_mob… |
| 98 | Corporate Action and Dividend P&L | N | P3 | - |
| 99 | Market Holiday and Trading Calendar Validation | P → W | P1 | NEW backtest/nse_calendar.py (2026 NSE list, 2 sources); garud_health uses it; options use exchange expiry … |
| 100 | Daily Trading Summary and Exception Report | W | - | Telegram per run with errors; PIPELINE_RUN heartbeat; Health 'recent data issues' |

### K. ML validation

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 101 | Strict Time-series Splits | W | - | evidence_matrix split_date; ml_lab train-first-5-years |
| 102 | Purged/Embargoed Validation | P | P3 | ml_lab uses only labels already known (k-1 month embargo) |
| 103 | Walk-forward Validation | W | - | ml_lab walk_forward_scores; backtest/walk_forward.py (Tools, untested) / 22 Oct (2): backtest/walk_forward.… |
| 104 | Data Leakage Detection | W | - | test_ml_lab strict no-look-ahead test |
| 105 | Multiple-testing / Selection Bias Review | P | P3 | Pre-registration of every study; handbook lessons table |
| 106 | Out-of-sample and Regime Results | W | - | evidence_matrix test split; longterm last-5-years window; ML 10-year OOS |
| 107 | Model Drift and Data Drift Monitoring | N | P3 | No ML model in production |
| 108 | ML Model Versioning and Rollback | N | P3 | No ML model in production |
| 109 | Prediction Confidence Calibration | N | P3 | - |
| 110 | Comparison against Simple Baselines | W | - | ML_LAB vs M2 rule vs NIFTY vs FD |

### L. Execution safety

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 111 | Market-open/close State Validation | W | - | paper_rule MARKET_OPEN/ENTRY_CUTOFF/PRE_CLOSE windows; completed_bars() |
| 112 | Trading Session and Timezone Correctness | W | - | IST everywhere (paper_rule.IST), close at 15:30 IST stored as UTC |
| 113 | Partial Fill and Cancel/Replace Handling | P | P3 (P0 before live) | live_executor cancels pending BUY on exit; sells only held qty |
| 114 | Broker/API Disconnect Detection | P | P2 | SandboxAuthError, SANDBOX_ORDER_FAILED events, Health broker check |
| 115 | Order Timeout and Unknown-state Recovery | P | P2 | unknown sandbox order reported; live holding check decides |
| 116 | Stale Signal Expiration | W | - | Entry only same morning (09:15-11:30) on today's open; stock last bar must match NIFTY date |
| 117 | Order Size / Quantity / Tick-size Validation | P | P3 (before live limit orders) | Whole shares; LIVE_MAX_ORDER_VALUE cap |
| 118 | Cash, Margin and Position Limit Checks | P | P3 (P0 before live) | live_guard capital/open/stock limits; momentum cash accounting |
| 119 | Manual Approval Mode | P | P3 | Momentum: Telegram list -> owner places orders manually (planned path) |
| 120 | Fail-safe Shutdown and Restart Recovery | W | - | State lives in Neon; missed runs caught up (due_month_ends, options settlement, rule exits replay bars) |

### M. UX & reporting

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 121 | Feature Status Dashboard | P | P3 | 🩺 Health tab; this inventory CSV |
| 122 | System Run History and Failure Timeline | W | - | PIPELINE_RUN events; Health 'recent data issues' |
| 123 | Data Source Status Dashboard | W | - | Health checks: NIFTY data, runs, broker, AI, risk, tokens |
| 124 | Strategy Configuration History | P | P3 | Rules frozen with registered_on (test_rules_are_frozen); git history |
| 125 | Configuration Validation | W | - | live_guard.problem()/config_problems() fail closed |
| 126 | Downloadable Sanitized Audit Report | P | P3 | docs/GARUD_* (this audit); weekly backup artifact |
| 127 | Explainable Risk Alerts | W | - | Risk tab texts; momentum drawdown/stale/sector alerts; options circuit breaker message |
| 128 | Daily System Health Report | P | P3 | Health tab on demand; per-run Telegram |
| 129 | User-friendly Gujarati/English Error Messages | W | - | advisor.friendly_error(); Gujarati UI errors |
| 130 | Separation of real, simulated and estimated values | W | - | PAPER badge, 'Paper trading — અસલ પૈસા નહીં', backtest labels; open P&L marked as estimate (new) |

### N. Deployment & maintenance

| ID | Feature | Before → After | Priority | Key evidence |
|---|---|---|---|---|
| 131 | Automated Smoke Tests | W | - | tests.yml compileall; momentum_dry_run.yml |
| 132 | Unit and Integration Test Coverage | P | P2 | 219 tests + UI stub test; no coverage % measured / 22 Oct (2): +6 tests for Tools modules; 229 tests total |
| 133 | Database Migration Tests | N | P3 | SQLAlchemy create_all, no migrations |
| 134 | Scheduler Duplicate-run Protection | W | - | rule_paper_trading.yml concurrency group; idempotent ids |
| 135 | Deployment Rollback | P | P3 | Git history; Streamlit redeploys main |
| 136 | Resource and Runtime Monitoring | P | P3 | Workflow timeouts; Health run age |
| 137 | Storage and Log Retention | P | P3 | Artifacts 90 days; audit_events unbounded |
| 138 | Automated Dependency Compatibility Checks | W | - | requirements upper bounds (test_repo_hygiene) + install in every Tests run |
