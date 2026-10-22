# GARUD SECURITY AUDIT — 22 Oct 2026 (no secrets in this file)

| Area | Finding | Status |
|---|---|---|
| Secrets in code | None. `tests/test_repo_hygiene.py` scans every .py/.yml/.toml/.txt/.md for JWT, Google API key and Telegram bot-token patterns | PASS |
| Where secrets live | GitHub Actions secrets (DATABASE_URL, TELEGRAM_*, UPSTOX_SANDBOX_TOKEN, UPSTOX_ANALYTICS_TOKEN) and Streamlit secrets (DB, Gemini). The classic GitHub token is used only by cron-job.org | PASS (by design; values not inspected) |
| Live trading isolation | Live orders need TRADING_MODE in (CONTROLLED_LIVE, LIVE) **and** LIVE_ORDERS_ENABLED **and** LIVE_RULES **and** LIVE_START_DATE. Only `rule_paper_trading.yml` can see LIVE_* variables. A set-but-invalid limit blocks every BUY (fail closed) | PASS (tests/test_live_gates.py, test_live_guard.py, test_repo_hygiene.py) |
| Kill switch | `GARUD_KILL_SWITCH=ON` stops all new BUYs in paper, options and live; exits continue | PASS |
| Status output | Live status and health checks never print secret values | PASS (test_live_gates::test_status_never_contains_secrets) |
| Workflow permissions | Tests workflow: `contents: read`. No workflow pushes to the repo | PASS |
| AI authority | `llm/advisor.py` and `llm/ask_garud.py` never import broker code; prompts forbid recommendations | PASS |
| Public app link and Gemini quota | The Streamlit link is public. Anyone with it can read paper data and use Ask Garud and the AI explanation. Ask Garud is capped at 30 questions per day | RISK — Low. No money or secrets exposed. **Recommendation:** make the Streamlit app private (Streamlit settings → Sharing) if paper data should stay private |
| Dependency vulnerabilities | No check existed. Added a pip-audit report to the Tests run | NEW, report only |
| Token expiry | `backtest/check_tokens.py` warns 5 days before expiry (Telegram and Health) | PASS. Sandbox token expires 29 Oct 2026; the owner must renew it |
| Database backup | Weekly artifact (90 days) plus the new restore drill | PASS after fix |
| Credential rotation | Manual (sandbox token monthly, analytics token yearly) | ACCEPTED |

**Owner rules (unchanged):**
- Never paste a token in chat or send a screenshot that contains one.
- Never set any LIVE_* variable until the handbook section 5 conditions are met.
