from models.predictive_model import ModelPrediction, PredictiveModel


class ModelEnsemble:
    def __init__(self, models: list[PredictiveModel]):
        self.models = models

    def predict(self, symbol: str, feature_vector: dict[str, float]) -> ModelPrediction:
        raise NotImplementedError
