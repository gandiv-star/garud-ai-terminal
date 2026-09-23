from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import Settings
from database.models import AuditEvent, TradeRecord

Base = declarative_base()


class TradeRecordORM(Base):
    __tablename__ = "trades"

    internal_order_id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    strategy_name = Column(String, nullable=False)
    strategy_version = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    ai_score = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    risk_amount = Column(Float, nullable=False)
    regime = Column(String, nullable=False)
    sector = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    broker_order_id = Column(String, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_timestamp = Column(DateTime, nullable=True)
    realized_pnl = Column(Float, nullable=True)


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String, nullable=False)
    symbol = Column(String, nullable=True)
    payload = Column(JSON, nullable=False)


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine = None
        self._session_factory = None

    def connect(self) -> None:
        self._engine = create_engine(self.settings.database_url)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

    def _session(self):
        if self._session_factory is None:
            self.connect()
        return self._session_factory()

    def save_trade(self, trade_record: TradeRecord) -> None:
        session = self._session()
        try:
            orm_record = TradeRecordORM(**trade_record.__dict__)
            session.merge(orm_record)
            session.commit()
        finally:
            session.close()

    def update_trade_exit(self, internal_order_id: str, exit_price: float, exit_timestamp, realized_pnl: float) -> None:
        session = self._session()
        try:
            row = session.query(TradeRecordORM).filter_by(internal_order_id=internal_order_id).first()
            if row is None:
                raise ValueError(f"No trade found with internal_order_id={internal_order_id}")
            row.exit_price = exit_price
            row.exit_timestamp = exit_timestamp
            row.realized_pnl = realized_pnl
            session.commit()
        finally:
            session.close()

    def save_audit_event(self, audit_event: AuditEvent) -> None:
        session = self._session()
        try:
            orm_event = AuditEventORM(
                timestamp=audit_event.timestamp,
                event_type=audit_event.event_type,
                symbol=audit_event.symbol,
                payload=audit_event.payload,
            )
            session.add(orm_event)
            session.commit()
        finally:
            session.close()

    def get_trades(self, limit: int = 50) -> list:
        session = self._session()
        try:
            rows = (
                session.query(TradeRecordORM)
                .order_by(TradeRecordORM.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                TradeRecord(
                    internal_order_id=r.internal_order_id, symbol=r.symbol,
                    strategy_name=r.strategy_name, strategy_version=r.strategy_version,
                    decision=r.decision, ai_score=r.ai_score, entry_price=r.entry_price,
                    stop_price=r.stop_price, target_price=r.target_price, quantity=r.quantity,
                    risk_amount=r.risk_amount, regime=r.regime, sector=r.sector,
                    timestamp=r.timestamp, broker_order_id=r.broker_order_id,
                    exit_price=r.exit_price, exit_timestamp=r.exit_timestamp,
                    realized_pnl=r.realized_pnl,
                )
                for r in rows
            ]
        finally:
            session.close()
