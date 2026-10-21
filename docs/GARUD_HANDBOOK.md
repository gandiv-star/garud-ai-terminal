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

**પહેલી momentum ખરીદી: 2 નવેમ્બર 2026 સાંજે** (30 ઓક્ટોના ભાવ પરથી પસંદગી).

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

Backtest ના આંકડા (યાદ રાખવા): M2 — 24.6%/વર્ષ, ઘટાડો 18.5% (આજનું NIFTY 200 લિસ્ટ → વધુ પડતું સારું; NSE ના સાચા Momentum index નો લાંબો ગાળો ~17–18%, છેલ્લા 5 વર્ષ ~9%). G — 11.4%/વર્ષ, ઘટાડો 17%. NIFTY — 11.7%, ઘટાડો 36%. FD — 7%.
**Tax ગણ્યો નથી** (દર મહિને ફેરફાર → મોટેભાગે short-term tax).

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

**Rehearsal:** Actions → "Momentum paper dry run" → Run workflow — અસલ ભાવ પર momentum નો પૂરો અભ્યાસ, કંઈ સાચવતું નથી. ગમે ત્યારે ચકાસી શકાય.

---

## 7. આગળનો roadmap (જ્યારે ફરી કામ શરૂ થાય)

1. Engine 2 — swing 2.0: મજબૂત momentum શેરમાં ઘટાડે ખરીદી (અનુભવી trader ની રીત) — 15 વર્ષ portfolio test.
2. AI allocator — mode પ્રમાણે engines વચ્ચે પૈસાની વહેંચણી (Momentum / Swing / Options / Liquid).
3. Momentum M2 માટે સાચું (point-in-time) NIFTY 200 લિસ્ટ — backtest નો પૂર્વગ્રહ દૂર કરવા.
4. Live માટે: static IP સર્વર, Upstox live token, compliance checklist (`docs/COMPLIANCE.md`).
