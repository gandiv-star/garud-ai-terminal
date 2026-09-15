from dataclasses import dataclass


@dataclass
class ModelPrediction:
    symbol: str
    prob_positive_return: float
    prob_stop_loss_hit: float
    expected_return: float
    expected_favorable_excursion: float
    expected_adverse_excursion: float


class PredictiveModel:
    def predict(self, symbol: str, feature_vector: dict[str, float]) -> ModelPrediction:
        raise NotImplementedError

    def fit(self, training_data) -> None:
        raise NotImplementedError
