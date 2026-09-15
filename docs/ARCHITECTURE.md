Architecture Notes
Pipeline (one-way, risk-gated):
data → features → regime → sector → strategies → scoring → models → risk → portfolio → execution → brokers → database → analytics
llm/, safety/, audit/, and security/ are cross-cutting modules — used by multiple stages rather than sitting in the linear pipeline.
Suggested Build Order:
core/ + config/ — modes, shared enums, settings loading (done)
data/ — market data loader + data quality validator
database/ — schema for trades, positions, audit events
regime/ — market regime detection
sector/ — sector relative-strength analysis
strategies/ — one module per strategy, independently testable
scoring/ + models/ — combine signals into an explainable score
risk/ — position sizing, dynamic stop-loss, exit engine
portfolio/ — correlation and sector-exposure checks
safety/ — daily loss limit + global kill switch
backtest/ — realistic backtesting + walk-forward validation
execution/ + brokers/ — broker abstraction, order placement
llm/ — news/event pipeline and trade explanations
analytics/ + audit/ — performance metrics, decision reconstruction
security/ — hardening before any live-money mode is enabled
Paper trading (PAPER mode) must be exercised end-to-end before CONTROLLED_LIVE is ever turned on, and CONTROLLED_LIVE before LIVE.
Open Decisions:
Persistence: SQLite vs. Postgres
Whether there's a UI, and what kind
Which broker(s) to integrate first — verify current official API docs
ML stack: start simple, escalate only if proven necessary
Compliance Reminder:
Nothing in this repo should be treated as SEBI/NSE/BSE-compliant until explicitly verified against current official sources.
