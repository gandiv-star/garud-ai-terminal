# Garud AI Terminal — ચલાવવાની પુસ્તિકા (21 ઓક્ટો 2026)

Garud પોતાની મેળે ચાલે છે: GitHub Actions (કામ), Neon (database), Streamlit (app), Telegram (સંદેશા).
કોઈ AI ની હાજરી વગર પણ બધું ચાલતું રહે છે. **અસલ પૈસાનું trading બંધ છે** અને આ પુસ્તિકા પ્રમાણે જ ચાલુ થઈ શકે.

---

## 1. આપમેળે શું ચાલે છે

| શું | ક્યારે | ક્યાં દેખાય |
|---|---|---|
| v1 / v2 / v3 swing paper rules | સોમ–શુક્ર 09:40, 09:55, 11:10, 14:40, 15:05, 17:00 | Telegram, app 📈 Trades |
| Upstox sandbox orders (paper ની નકલ) | એ જ runs માં | Telegram 🧪 |
| NIFTY options iron condor (paper) | બુધ–શુક્ર 09:30–11:30 entry, expiry સુધી દેખરેખ | Telegram 🎯, app 🎯 Options |
| **Momentum paper — M2 (₹3 લાખ, 20 શેર) અને G (₹1 લાખ, 10 શેર)** | મહિનાના છેલ્લા દિવસના ભાવે પસંદગી, બીજા કામકાજના દિવસે સાંજે ખરીદી; રોજ સાંજે કિંમત | Telegram 📦, app 🔬 સંશોધન |
| Token expiry ચેતવણી | દરેક run | Telegram 🔑 (5 દિવસ પહેલાં) |
| Tests | દરેક upload પછી | GitHub → Actions → Tests |
| Database backup (બધા trades + events) | દર રવિવારે 18:00 | Telegram 💾, Actions → "Database backup (weekly)" → Artifacts (90 દિવસ) |
| Momentum ચેતવણીઓ | rebalance / રોજ સાંજે | 📦 સંદેશમાં sector હિસ્સો; ખાતું ટોચથી 15% નીચે જાય કે ભાવ 6+ દિવસ જૂના હોય તો ⚠️ (જૂના ભાવ પર rebalance થતું જ નથી) |

**પહેલી momentum ખરીદી: 2 નવેમ્બર 2026 સાંજે** (30 ઓક્ટોના ભાવ પરથી પસંદગી).

**App માં (માત્ર માહિતી):** 🤖 પૂછો — Garud ના પોતાના આંકડા પરથી ગુજરાતીમાં જવાબ (Gemini; order/નિયમ બદલવાની સત્તા નહીં; દરેક જવાબ ASK_GARUD તરીકે database માં; દિવસે 30 પ્રશ્ન). 🧭 Mode tab નીચે "બજારનું વાતાવરણ": India VIX, ડૉલર-રૂપિયો, crude, US yield, સોનું, NIFTY 50 ના કેટલા શેર 200-દિવસ સરેરાશથી ઉપર.

---

## 2. Telegram સંદેશાનો અર્થ

- 🟢 / 🔴 = paper trade ખુલ્યો / બંધ થયો (અસલ પૈસા નહીં)
- 🧪 = sandbox (Upstox નું test ખાતું) order
- 📦 = momentum paper portfolio: ખરીદ/વેચ યાદી, કિંમત, NIFTY સાથે સરખામણી
- 🎯 = options condor
- ⚠️ "run FAILED" = GitHub પર કંઈક અટક્યું. **એક વાર** Actions ખોલી "Run workflow" (source: manual) ફરી ચલાવો. ફરી નિષ્ફળ થાય તો નીચેનો વિભાગ 6 જુઓ.
- 🔑 = token પૂરો થવામાં છે — વિભાગ 3

---

## 3. મહિને એક વાર કરવાનું (માત્ર આ જ)

**Upstox SANDBOX token — દર 30 દિવસે** (હાલનો 29 ઓક્ટો 2026 એ પૂરો થાય છે)
1. Upstox Developer પર તમારી sandbox app ("API Sandbox") ખોલો → નવો token બનાવો.
2. GitHub → repo → Settings → Secrets and variables → Actions → `UPSTOX_SANDBOX_TOKEN` → Update → નવો token paste → Save.
3. Token ક્યારેય chat, screenshot કે code માં ન મૂકવો.
Token ન બદલો તો પણ paper trading ચાલુ રહે છે — માત્ર sandbox નકલ બંધ થાય છે.

બીજા tokens: Upstox ANALYTICS token (options માટે) — 23 સપ્ટે 2027 સુધી. Gemini key — Streamlit secrets માં.

---

## 4. નિર્ણયનું સમયપત્રક

| શું | ક્યારે નિર્ણય | નિયમ |
|---|---|---|
| v1 / v2 / v3 swing rules | દરેકના 30 બંધ trades પછી | net > 0, PF ≥ 1.15, backtest થી બહુ નીચે નહીં → PASS. (15 વર્ષના portfolio test માં swing નબળું નીકળ્યું — અસલ પૈસાની અપેક્ષા ઓછી.) |
| Options condor | 30 condors પછી (circuit breaker −₹15,000) | પહેલાંથી નક્કી શરતો |
| **Momentum M2 / G** | **ફેબ્રુઆરી 2027** (3 મહિના) | paper નું વર્તન backtest જેવું હોય તો નાની રકમથી અસલ શરૂઆત — નિર્ણય તમારો. M2 ને 20 શેર માટે ઓછામાં ઓછા ~₹3 લાખ જોઈએ (₹1 લાખમાં આખા શેરના કારણે ~40% રકમ રોકડ રહી જાય — 21 ઓક્ટો dry run). ઓછી રકમ હોય તો G (10 શેર) વધુ યોગ્ય. |

**ખર્ચ (નિર્ણય A, 22 ઓક્ટો):** 23 ઓક્ટો 2026 થી ખુલતા દરેક paper trade (swing અને momentum) Upstox ના સાચા delivery ખર્ચે ગણાય છે — ₹20/order + વેચાણ પર ₹20+GST DP. તે પહેલાંના trades જૂની રીતે જ રહે છે. Cost re-check (tax + સાચા ખર્ચ પછી, ₹3 લાખ): M2 21.18%, G 9.74%, NIFTY ETF 10.95%; ₹1 લાખ: M2 20.79%, G 9.10%, ETF 11.11%. Swing rules ના 30-trade નિર્ણય માટે માપદંડ (benchmark v1) બદલાયો નથી; સાચા ખર્ચવાળું backtest v3 માહિતી માટે ("Rule benchmark v2 + v3" workflow).

Backtest ના આંકડા (યાદ રાખવા): M2 — 24.6%/વર્ષ, ઘટાડો 18.5% (આજનું NIFTY 200 લિસ્ટ → વધુ પડતું સારું; NSE ના સાચા Momentum index નો લાંબો ગાળો ~17–18%, છેલ્લા 5 વર્ષ ~9%). G — 11.4%/વર્ષ, ઘટાડો 17%. NIFTY — 11.7%, ઘટાડો 36%. FD — 7%.
ઉપરના આંકડા **tax પહેલાંના** છે. Tax પછીનો આંકડો: Actions → "After-tax comparison (15 years)" → Run workflow (ધારણા: કુલ આવક ₹12 લાખ સુધી → FD/liquid પર tax નહીં; શેર: short-term 20%, long-term 12.5% ₹1.25 લાખ ઉપર; આજના નિયમ બધા વર્ષે). અંતિમ ખાતરી CA પાસે.

---

## 5. સલામતીના નિયમો (ક્યારેય ન તોડવા)

- **Kill switch:** GitHub → Settings → Secrets and variables → Actions → **Variables** → `GARUD_KILL_SWITCH` = `ON` → નવી ખરીદી બંધ (વેચાણ ચાલુ). ફરી શરૂ કરવા `OFF`.
- **અસલ પૈસા (live)** ત્યારે જ: (1) કોઈ strategy paper માં PASS, (2) static IP વાળું સર્વર, (3) રોજનો Upstox live token. ત્યાં સુધી `TRADING_MODE`, `LIVE_ORDERS_ENABLED`, `LIVE_RULES`, `LIVE_START_DATE` **ક્યારેય સેટ ન કરો**.
- Live limit variables (LIVE_CAPITAL વગેરે) માં **માત્ર આંકડા** — `100000`, `1,00,000` નહીં. ખોટું લખાય તો Garud જાતે ખરીદી રોકી દે છે અને Telegram પર જણાવે છે.
- Secrets/token માત્ર GitHub Secrets અને Streamlit secrets માં.

---

## 6. કંઈ બગડે તો

1. Actions → નિષ્ફળ run → લાલ step ખોલો → screenshot (એમાં token હોતો નથી).
2. Garud ના paper records database માં સુરક્ષિત છે; એક-બે run નિષ્ફળ જાય તો પણ momentum અને swing rules પછીના run માં આપમેળે પકડી લે છે.
3. મદદ માટે કોઈ પણ AI ને આ પુસ્તિકા + `docs/` folder + screenshot આપો. Repo: `gandiv-star/garud-ai-terminal`.
4. ફેરફાર પછી હંમેશા Actions → Tests લીલું હોવું જોઈએ.

**Database ગુમ થાય / બગડે તો (backup થી પાછું):**
1. Actions → "Database backup (weekly)" → છેલ્લો સફળ run → Artifacts → `garud-db-backup` download (અંદર `garud_backup_YYYYMMDD.json.gz`). દર રવિવારના Telegram માં "Restore drill OK" હોય તે backup ભરોસાપાત્ર છે.
2. Neon માં નવો database બનાવો → તેની connection string GitHub Secrets અને Streamlit secrets માં `DATABASE_URL` તરીકે બદલો (chat માં ક્યારેય ન મૂકવી).
3. App/run પહેલી વાર ચાલતાં ખાલી tables (`trades`, `audit_events`) આપમેળે બને છે.
4. Backup file ની JSON માંથી rows પાછી નાખવા કોઈ પણ AI ને આ પુસ્તિકા + file આપો: `trades` ની દરેક row અને `audit_events` ની દરેક row (id સિવાય) એ જ નામના columns માં insert કરવાની છે; `backup_db.restore_drill()` જેવી જ ગણતરી પછી મેળવી જોવી.

**એક વાર ચલાવવાના અભ્યાસ (Actions → Run workflow, પરિણામ Telegram + 🔬 સંશોધન):** "M2 robustness check" (6 settings, bootstrap, NIFTY 200 અને Momentum 30 ETF સાથે સરખામણી) · "AI/ML Lab" (gradient-boosted trees vs M2 નિયમ, walk-forward) · "After-tax comparison" (M2 / G / NIFTY ETF / FD, tax પછી, ₹3 લાખ) · "Cost re-check (Upstox 2026 charges)" (₹20/order + DP charge સાથે ફરી ગણતરી — paper trading બદલાતું નથી).

**Rehearsal:** Actions → "Momentum paper dry run" → Run workflow — અસલ ભાવ પર momentum નો પૂરો અભ્યાસ, કંઈ સાચવતું નથી. ગમે ત્યારે ચકાસી શકાય.

---

## 7. અત્યાર સુધી શું ચકાસાયું (ફરી ન કરવું)

| શું | પરિણામ (15 વર્ષ, ખર્ચ સહિત) | શીખ |
|---|---|---|
| Intraday (60-min) | ❌ ખર્ચ ~₹180/trade નફો ખાઈ જાય | |
| Swing v1/v2/v3 (એક ખાતામાં) | ❌ v3: 4.4%/વર્ષ, ઘટાડો 35% | |
| Regime પ્રમાણે strategy પસંદગી | ❌ પુરાવો નથી | |
| **Engine 2 — Swing 2.0** (મજબૂત શેરમાં 5% ઘટાડે ખરીદી, 21 ઓક્ટો) | ❌ NIFTY 50: −1.8% થી +0.9%/વર્ષ, ઘટાડો 35–51% | ~1,500–4,000 ટૂંકા trades: delivery STT (0.1% બંને બાજુ) + slippage નફો ખાઈ જાય. **નબળા બજારના trades દરેક રીતમાં નુકસાનમાં** → "નબળા બજારમાં ખરીદી બંધ" નિયમ સાચો |
| ✅ Momentum G / M2 + નબળા બજારમાં બહાર | પાસ (વિભાગ 4) | મહિને એક વાર ફેરફાર → ઓછો ખર્ચ |

**મુખ્ય શીખ:** ભારતમાં delivery માં વારંવાર ખરીદ-વેચાણ ખર્ચના કારણે નુકસાન કરે છે. ઓછા trades + મજબૂત શેર + નબળા બજારમાં બહાર = એકમાત્ર પાસ થયેલી રીત.

## 8. આગળનો roadmap (જ્યારે ફરી કામ શરૂ થાય)

1. Momentum M2/G નું paper પરિણામ (ફેબ્રુઆરી 2027) → નાની રકમથી અસલ શરૂઆત (static IP વગર પણ શક્ય: મહિને એક વાર Telegram યાદી પ્રમાણે જાતે orders, ~10 મિનિટ).
2. Momentum M2 માટે સાચું (point-in-time) NIFTY 200 લિસ્ટ — backtest નો પૂર્વગ્રહ દૂર કરવા.
3. ✅ Tax પછીનું વળતર — તૈયાર (21 ઓક્ટો). Tax ના નિયમ બદલાય તો `backtest/tax_study.py` માં STCG / LTCG / LTCG_EXEMPT બદલવા.
4. AI allocator — mode પ્રમાણે Momentum / Options / Liquid વચ્ચે વહેંચણી (options condor ના 30 trades પછી).
5. Live (આપમેળે orders) માટે: static IP સર્વર, Upstox live token, compliance checklist (`docs/COMPLIANCE.md`).

## 9. Audit (22 ઓક્ટો 2026)

140 features ની પુરાવા સાથેની ચકાસણી, પ્રાથમિકતા અને આગળનું કામ: `docs/GARUD_*` files (શરૂઆત `GARUD_MASTER_AUDIT.md` અને `GARUD_NEXT_SESSION_HANDOFF.md` થી). દર વર્ષે ડિસેમ્બરમાં NSE ની નવા વર્ષની રજાઓ `backtest/nse_calendar.py` માં ઉમેરવી.
