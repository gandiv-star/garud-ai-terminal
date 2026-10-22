# GARUD DEPENDENCIES AND BLOCKERS — 22 Oct 2026

## External services

| Service | Used for | Status | Owner action |
|---|---|---|---|
| GitHub Actions | All automation | Working | — |
| cron-job.org | On-time dispatch (classic GitHub token) | Working | Keep the token only there |
| Neon Postgres | trades / audit_events | Working (free tier) | — |
| Streamlit Cloud | App | Working (public link) | Optional: make the app private |
| Telegram bot | Alerts | Working | — |
| yfinance (Yahoo) | All equity prices, NIFTY, macro | Working. Single source | — |
| Upstox sandbox | Order mirror | Working. **Token expires 29 Oct 2026** | Renew (handbook section 3) |
| Upstox analytics | Option chains | Working until 23 Sep 2027 | — |
| Gemini | AI explanations, Ask Garud | Working | — |

## Python packages
`requirements.txt` has 12 packages, each with an upper cap. A pip-audit vulnerability report is now in every Tests run.

## Blockers

| Blocked item | Needs | Feature IDs |
|---|---|---|
| Automatic live orders | Static IP server, a daily Upstox live token, a strategy PASS, and the compliance re-check | 48, 63, 140 |
| Options backtest | Paid historical option-chain data | 50 |
| Earnings / results filter | A reliable free corporate-events calendar | 35 |
| Point-in-time NIFTY 200 list | Historical index constituent files (NSE archives) | 2 (bias) |
| Paper P&L on real broker charges | **Owner approval** (changes existing paper P&L basis) | P0 cost finding |
| Gap-aware paper stops | **Owner approval** | 14 |

## What this audit could not verify (no access from the cloud workspace)
- Live database contents (stored benchmark PFs, sandbox order counts).
- GitHub run logs.
- Yahoo data from inside the workspace.
- pip-audit results.

All of these are marked UNVERIFIED-today in the master audit.
