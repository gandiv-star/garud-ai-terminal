from dataclasses import dataclass


@dataclass
class WalkForwardWindow:
    train_start: str
    train_end: str
    validation_end: str
    out_of_sample_end: str


class WalkForwardValidator:
    def generate_windows(
        self, start_date: str, end_date: str, train_days: int, validation_days: int, oos_days: int
    ) -> list[WalkForwardWindow]:
        raise NotImplementedError

    def run(self, strategy, windows: list[WalkForwardWindow]) -> list[dict]:
        raise NotImplementedError
