from dataclasses import dataclass, field
from datetime import datetime

from data.data_loader import Bar


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[str] = field(default_factory=list)


class DataValidator:
    def validate_bars(self, symbol: str, bars: list[Bar]) -> ValidationResult:
        issues: list[str] = []

        if not bars:
            return ValidationResult(is_valid=False, issues=["no_data"])

        for bar in bars:
            if bar.high < bar.low:
                issues.append(f"{symbol}: high < low at {bar.timestamp}")
            if not (bar.low <= bar.open <= bar.high):
                issues.append(f"{symbol}: open outside high/low at {bar.timestamp}")
            if not (bar.low <= bar.close <= bar.high):
                issues.append(f"{symbol}: close outside high/low at {bar.timestamp}")
            if bar.volume < 0:
                issues.append(f"{symbol}: negative volume at {bar.timestamp}")

        timestamps = [b.timestamp for b in bars]
        if len(timestamps) != len(set(timestamps)):
            issues.append(f"{symbol}: duplicate timestamps present")

        return ValidationResult(is_valid=len(issues) == 0, issues=issues)

    def is_stale(self, symbol: str, latest_bar: Bar, max_staleness_seconds: int) -> bool:
        if latest_bar.timestamp.tzinfo is not None:
            now = datetime.now(latest_bar.timestamp.tzinfo)
        else:
            now = datetime.now()
        age_seconds = (now - latest_bar.timestamp).total_seconds()
        return age_seconds > max_staleness_seconds
