from config.settings import Settings


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._connection = None

    def connect(self) -> None:
        raise NotImplementedError

    def save_trade(self, trade_record) -> None:
        raise NotImplementedError

    def save_audit_event(self, audit_event) -> None:
        raise NotImplementedError
