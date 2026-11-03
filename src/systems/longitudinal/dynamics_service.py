from .exceptions import InvalidVisitPayloadError
from .metrics_extractor import MetricsExtractor
from .trend_calculator import TrendCalculator
from src.schemas.contracts import S5Out


class DynamicsService:
    """
    Calculate longitudinal metric trends using a dict -> dict contract.

    Input:
        {
            "visits": ...,
        }

    Output:
        {
            "trends": ...,
        }
    """

    def __init__(self, extractor: MetricsExtractor, calculator: TrendCalculator):
        self.extractor = extractor
        self.calculator = calculator

    def calculate(self, input_data: dict) -> dict:
        """
        Extract metrics from raw visits and return validated trend data.
        """
        if not isinstance(input_data, dict):
            raise InvalidVisitPayloadError(
                f"Expected input data to be a dict, got {type(input_data).__name__}."
            )

        visits = input_data.get("visits")
        if not isinstance(visits, list):
            raise InvalidVisitPayloadError(
                f"Expected 'visits' to be a list of dicts, got {type(visits).__name__}."
            )

        if not visits:
            return S5Out(trends=[]).model_dump()

        grouped_data = self.extractor.extract(visits)

        trends = [
            self.calculator.build_trend_dict(metric, data)
            for metric, data in grouped_data.items()
        ]

        return S5Out.model_validate({"trends": trends}).model_dump()