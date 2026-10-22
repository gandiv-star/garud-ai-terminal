# Garud — Live-readiness and broker permission audit (22 Oct 2026)

**No real-money order has ever been placed.** Live trading is OFF. This file lists what must be true before
that changes. The same checklist is shown in the app (🩺 Health → "Live-readiness checklist"), computed from
`backtest/live_readiness.py`.

## 1. Broker permission audit (what each credential can do, from the code)

| Credential (where stored) | Used by | API calls Garud makes | Can it move money? |
|---|---|---|---|
| `UPSTOX_ANALYTICS_TOKEN` (GitHub secret) | `backtest/options_paper.py` | Read option contracts and chains (`/option/contract`, `/option/chain`) | No: read-only analytics token |
| `UPSTOX_SANDBOX_TOKEN` (GitHub secret) | `backtest/sandbox_mirror.py`, `brokers/upstox_sandbox.py` | Place orders in the Upstox **sandbox** (test account) | No: sandbox only, no real money |
| `BROKER_ACCESS_TOKEN` (**not set**) | `brokers/upstox_live.py` via `backtest/live_executor.py` | place/cancel order, GTT place/cancel, order details, positions, holdings, funds | **Yes.** Only when ALL live gates are open (see 2) |
| `GEMINI_API_KEY` (Streamlit secret) | `llm/advisor.py`, `llm/ask_garud.py` | Text generation | No: never imports broker code (tested) |
| `TELEGRAM_*` (GitHub secrets) | runners | Send messages | No |
| `DATABASE_URL` (GitHub + Streamlit secrets) | everything | Read/write paper records | No |
| Classic GitHub token (cron-job.org only) | cron-job.org | Start the `rule_paper_trading` workflow | No. **Recommendation:** replace it with a fine-grained token limited to this repo with only "Actions: read and write" |

Least privilege today:
- Only the rule workflow can see `LIVE_*` settings (`tests/test_repo_hygiene.py`).
- The options step always runs in paper mode (`tests/test_live_gates.py::test_options_step_is_always_paper`).

## 2. Gates in code (all required for one real order)
1. `TRADING_MODE` = CONTROLLED_LIVE or LIVE.
2. `LIVE_ORDERS_ENABLED=YES`.
3. `LIVE_RULES` lists a rule that PASSED.
4. `LIVE_START_DATE` is set.
5. `GARUD_KILL_SWITCH` is not ON.
6. All live limits are valid (fail closed).
7. Order value ≤ `LIVE_MAX_ORDER_VALUE`.
8. The portfolio guard (capital, open positions, % per stock, monthly loss) allows it.
9. Available cash at the broker covers it (blocked if unknown).
10. Tested in `tests/test_live_gates.py`, `test_live_guard.py`, `test_live_executor.py` and `test_execution_safety.py`.

## 3. Checklist status (22 Oct 2026)

| Item | Status |
|---|---|
| A strategy PASSED its paper test | TODO: swing rules have fewer than 30 trades; v2 loses money in benchmark v3. Momentum decision Feb 2027 |
| Live switches OFF | OK |
| Live limits valid | OK |
| Execution safety built and tested | OK (fake broker only; never exercised with real money) |
| Order rate below 10/s | OK by design |
| Compliance checklist re-checked within 60 days | TODO: last review Sep 2026. Re-check `docs/COMPLIANCE.md` before going live |
| Static IP server | MANUAL: not set up |
| Upstox algo onboarding and Algo-ID | MANUAL: confirm with Upstox |
| Daily live token process | MANUAL: not set up |
| Weekly restore drill | MANUAL: Sunday Telegram |

**The simplest real-money path (no static IP, no automation):**
- In Feb 2027, if momentum M2/G paper results are consistent with the backtest, the owner places the monthly orders by hand from the Telegram list (about 10 minutes a month).
- None of the live gates above are involved.
