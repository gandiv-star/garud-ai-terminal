# Compliance Checklist — Retail Algo Trading (India)

**This is informational, not legal advice.** Claude is not a lawyer or
compliance professional. Verify current specifics directly with your
broker (Upstox) and, if this ever scales beyond personal use, a SEBI
compliance professional, before enabling any live order placement.

Last researched: September 2026. Regulations in this area have changed
significantly in the last 18 months and may change again — re-verify
before relying on anything below.

## The governing framework

- **SEBI Circular SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/0000013** (Feb 4,
  2025) — "Safer participation of retail investors in Algorithmic
  trading."
- Rolled out via a phased glide path (broker registration milestones
  Oct 2025 – Jan 2026); **the full framework became mandatory for all
  stockbrokers on April 1, 2026** — i.e. it is already fully in force.
- Implemented operationally via NSE/BSE circulars (e.g. NSE circular
  INVG67858) that set the technical standards brokers must enforce.

## Where Garud AI Terminal sits today

Garud is currently in **PAPER mode only** — no live orders are placed,
so most of the obligations below do not yet apply. They become
relevant the moment `TRADING_MODE` is switched toward `CONTROLLED_LIVE`
or `LIVE`.

## Checklist

- [ ] **Static IP.** Confirmed already: Upstox requires a registered
  static IP (primary, optionally a secondary for redundancy) for
  API-based order/portfolio access. This is a hard NSE/SEBI-mandated
  requirement, not an Upstox-specific choice. (Deferred — see the
  "Future Pending Phase" note in this repo's project history.)

- [ ] **Order rate — the 10 OPS threshold.** A "tech-savvy retail
  investor" trading their own account, generating fewer than 10 Orders
  Per Second (per exchange, per client), is understood not to require
  formal exchange strategy registration as an "Algo Provider." Garud's
  design (one analysis → one order at a time, human-triggered) is far
  below this threshold by construction. If this ever changes (e.g.
  fully automated multi-symbol order bursts), re-check this threshold
  specifically.

- [ ] **Algo-ID / order tagging.** From April 1, 2026, every
  algorithmic order must carry an exchange-issued Algo-ID so it can be
  traced back to the originating strategy. This tagging is implemented
  broker-side (Upstox assigns/attaches it when an API order is placed)
  — confirm with Upstox's API docs exactly how this is exposed (e.g.
  a required field on the order-placement payload) before wiring
  `brokers/upstox_broker.py`'s order placement methods.

- [ ] **"Algo Provider" status.** This applies to entities offering
  algo strategies to *other* people via API (SaaS platforms, strategy
  marketplaces). Garud, used solely for GA's own account, should not
  trigger this — but if Garud is ever shared with or run on behalf of
  someone else's account, this changes materially and needs its own
  review.

- [ ] **Broker as Principal.** Upstox is legally responsible for every
  algorithm running on their API, and conducts its own due diligence /
  onboarding requirements for API/algo access. Confirm Garud's Upstox
  API access is provisioned under whatever "self-use retail algo"
  pathway Upstox currently offers (this may require enabling a
  specific setting or agreeing to specific terms in the Upstox
  developer console — check there directly).

- [ ] **Unique Client Code / KYC-linked API key.** Confirm the API key
  and access token used are tied to GA's own KYC'd trading account
  (not a shared/generic key) — this is a baseline broker requirement,
  independent of the algo-specific rules above.

- [ ] **Record-keeping.** Garud's own audit trail (`audit/audit_trail.py`,
  every trade's regime/score/risk/reason logged) already covers the
  spirit of SEBI's order-traceability intent at the application level.
  This does NOT substitute for the exchange-level Algo-ID tagging above
  — the two are complementary, not interchangeable.

## Before flipping TRADING_MODE to CONTROLLED_LIVE or LIVE

1. Re-run the searches this checklist is based on — rules in this area
   move fast; treat everything above as a starting point, not a final
   answer.
2. Confirm directly with Upstox (support or developer docs) exactly
   what retail-algo onboarding step, if any, is still needed on their
   side for API order placement specifically (as opposed to the
   read-only endpoints already scoped).
3. Confirm the Algo-ID field/requirement with Upstox's current order
   API reference before `brokers/upstox_broker.py` places its first
   real order.
