from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class OrderRequest:
    internal_order_id: str  # system-generated, unique — required for de-dup
    symbol: str
    exchange: str
    side: OrderSide
    quantity: int
    order_type: str  # e.g. MARKET, LIMIT
    price: float | None = None
    product_type: str | None = None


@dataclass
class OrderResult:
    internal_order_id: str
    broker_order_id: str | None
    status: OrderStatus
    filled_quantity: int = 0
    average_price: float | None = None
    raw_response: dict | None = None


class BaseBroker(ABC):
    @abstractmethod
    def authenticate(self) -> None: ...

    @abstractmethod
    def get_funds(self) -> dict: ...

    @abstractmethod
    def get_positions(self) -> list[dict]: ...

    @abstractmethod
    def get_holdings(self) -> list[dict]: ...

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResult: ...

    @abstractmethod
    def modify_order(self, broker_order_id: str, **changes) -> OrderResult: ...

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> OrderResult: ...

    @abstractmethod
    def get_order_status(self, broker_order_id: str) -> OrderResult: ...
