from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class KillSwitchEvent:
    reason: str
    triggered_at: datetime
    details: dict = field(default_factory=dict)


class KillSwitch:
    def __init__(self):
        self._engaged = False
        self._history: list[KillSwitchEvent] = []

    @property
    def engaged(self) -> bool:
        return self._engaged

    def trigger(self, reason: str, **details) -> None:
        self._engaged = True
        self._history.append(
            KillSwitchEvent(reason=reason, triggered_at=datetime.utcnow(), details=details)
        )

    def reset(self, authorized_by: str) -> None:
        """Resetting must be an explicit, attributable human action."""
        raise NotImplementedError

    def history(self) -> list[KillSwitchEvent]:
        return list(self._history)
