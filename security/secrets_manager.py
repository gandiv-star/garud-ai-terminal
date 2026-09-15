import os


class SecretsManager:
    @staticmethod
    def get(name: str, required: bool = True) -> str | None:
        value = os.getenv(name)
        if required and not value:
            raise RuntimeError(f"Missing required secret: {name}")
        return value
