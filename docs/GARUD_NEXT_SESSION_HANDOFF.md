# GARUD NEXT SESSION HANDOFF — written 22 Oct 2026

**Read first:**
- `docs/GARUD_HANDBOOK.md` (how Garud runs).
- `docs/GARUD_FEATURE_INVENTORY.csv` (the status of all 140 features).

## State at hand-off
- **Live trading:** OFF. Everything is paper or sandbox.
- **Tests:** 233 pass locally; GitHub "Tests" must be green after every upload.
- **Paper tests running:**
  - Swing v1/v2/v3: 30 trades each.
  - Options condor: 30 condors.
  - Momentum M2 (₹3L) and G (₹1L): first signal 30 Oct, first fill 2 Nov 2026, decision Feb 2027.
- **No strategy is proven profitable yet.**

## Waiting for the owner (decisions, not code)
1. **Cost model: DONE** (decision A approved 22 Oct; real charges from 23 Oct 2026). The owner should run Actions → "Rule benchmark v2 + v3" once to store benchmark v3.
2. **Gap-aware paper stops** (`paper_rule.GAP_AWARE_STOPS`): ON or OFF for new trades.
3. **Upstox sandbox token:** renew before 29 Oct 2026.

## Next highest-priority tasks (in order)
1. Confirm benchmark v3 was stored (Research tab, "Backtest સાચા ખર્ચે (v3)").
2. Check the first weekly backup with the restore drill (Sunday Telegram: "Restore drill OK").
3. Check the first pip-audit report in the Tests summary; raise caps for vulnerable packages if needed.
4. After 3 momentum rebalances (around Feb 2027), add the momentum decay check (inventory ID 8).
5. Remaining P2 list in `GARUD_PRIORITY_ROADMAP.md`. Done on 22 Oct: Tools tests, drawdown days, bootstrap fall-chance, spread recording, restore steps.
6. Add the NSE 2027 holiday list to `backtest/nse_calendar.py` when NSE publishes it (December).

## Rules for any future AI working on Garud
- Don't enable live trading.
- Don't change a registered rule after seeing results.
- Don't call anything profitable before its paper test passes.
- Don't rebuild features marked WORKING_VERIFIED.
- Ask the owner before any change that alters existing behaviour.
- The owner works from a phone:
  - Deliver files one by one, folder by folder.
  - Use Gujarati for messages.
  - Never ask for tokens in chat.
