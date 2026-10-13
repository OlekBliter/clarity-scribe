from .metrics_extractor import MetricsExtractor
from .trend_calculator import TrendCalculator

class DynamicsService:
    """Metric extraction and trend calculation for visit data."""

    def __init__(self, extractor: MetricsExtractor, calculator: TrendCalculator):
        self.extractor = extractor
        self.calculator = calculator

    def calculate(self, visits: list[dict]) -> dict:
        """
        Recieves a list of raw dict, manages the process of calculation, returns a dict
        """
        grouped_data = self.extractor.extract(visits)

        trends = [
            self.calculator.build_trend_dict(metric, data)
            for metric, data in grouped_data.items()
        ]

        return {"trends": trends}