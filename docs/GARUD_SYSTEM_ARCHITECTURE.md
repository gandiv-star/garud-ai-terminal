# GARUD SYSTEM ARCHITECTURE (as built, 22 Oct 2026)

```
 cron-job.org ──dispatch──┐        GitHub cron (backup timing)
                          ▼
              GitHub Actions: rule_paper_trading.yml   (concurrency group, 6 runs/day Mon–Fri)
                │ backtest/run_rule_paper.py
                ├─ paper_rule.run_all     swing v1/v2/v3 (yfinance → features → regime → rule → TradeRecord)
                ├─ sandbox_mirror.mirror  same orders to the Upstox SANDBOX (test account)
                ├─ live_executor          LIVE gates (all OFF) → live_guard limits → upstox_live
                ├─ options_paper.run      NIFTY iron condor (Upstox analytics API, paper)
                ├─ run_momentum_paper     M2 (₹3L) / G (₹1L) monthly paper portfolios
                ├─ check_tokens           expiry warnings
                └─ Telegram messages + PIPELINE_RUN heartbeat
                          │
                          ▼
              Neon Postgres: trades (paper swing) · audit_events (everything else, JSON payloads)
                          │
                          ▼
              Streamlit app (public link): streamlit_app.py → garud_mobile.py
                Home · Mode (+macro) · Scanner · Chart · Trades · Risk · Options · Research · 🤖 Ask · Health · Tools
                AI: llm/advisor.py (explain a scanner row) · llm/ask_garud.py (Q&A). Both read-only, Gemini
```

**One-time studies** (Actions → Run workflow; each writes a versioned event and sends Telegram):
- benchmark_v2, evidence_matrix
- portfolio_15y, momentum_200, swing2_15y, m2_robustness, ml_lab
- tax_study, **cost_recheck** (new)
- momentum_dry_run (rehearsal, writes nothing)

**Safety layers:**
1. TRADING_MODE=PAPER.
2. The live gates: LIVE_ORDERS_ENABLED + LIVE_RULES + LIVE_START_DATE, a static IP and a daily token.
3. `live_guard` limits, which fail closed.
4. Kill switch GARUD_KILL_SWITCH.
5. Options circuit breaker.
6. Momentum stale-price guard.

**Data:**
- yfinance (equities, NIFTY, macro).
- Upstox analytics (option chains).
- Upstox sandbox (order mirror).
- No paid data.

**Backup:** weekly gzip JSON artifact (90 days) plus a restore drill (new).

**Code map:**
- `backtest/`: all engines, studies and runners.
- `brokers/`: Upstox sandbox and live.
- `database/`: SQLAlchemy models.
- `llm/`: AI.
- `garud_*.py`: app screens and helpers.
- `strategies/`, `features/`, `regime/`, `sector/`, `scoring/`, `risk/`, `portfolio/`, `execution/`, `analytics/`: the original pipeline modules. Several are used only by the Tools tab and are untested (see the inventory).

Design notes: `docs/ARCHITECTURE.md` (original). Operations: `docs/GARUD_HANDBOOK.md`.
