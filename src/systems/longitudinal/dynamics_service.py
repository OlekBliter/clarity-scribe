from .exceptions import InvalidVisitPayloadError
from .metrics_extractor import MetricsExtractor
from .trend_calculator import TrendCalculator


class DynamicsService:
    """Metric extraction and trend calculation service for longitudinal visit data."""

    def __init__(self, extractor: MetricsExtractor, calculator: TrendCalculator):
        self.extractor = extractor
        self.calculator = calculator

    def calculate(self, visits: list[dict]) -> dict:
        """
        Receives a list of raw visit dictionaries, orchestrates trend calculation,
        and returns a dictionary matching the output contract.
        """
        if not isinstance(visits, list):
            raise InvalidVisitPayloadError(
                f"Expected 'visits' to be a list of dicts, got {type(visits).__name__}."
            )

        if not visits:
            return {"trends": []}

        grouped_data = self.extractor.extract(visits)

        trends = [
            self.calculator.build_trend_dict(metric, data)
            for metric, data in grouped_data.items()
        ]

        return {"trends": trends}