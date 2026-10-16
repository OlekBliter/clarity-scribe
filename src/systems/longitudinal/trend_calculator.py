import numpy as np
from .exceptions import TrendCalculationError

class TrendCalculator:
    """Calculate linear regression trends for a metric over time."""

    @staticmethod
    def _calculate_r_squared(y: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate the coefficient of determination R^2."""
        sse = np.sum((y - y_pred) ** 2)
        sst = np.sum((y - np.mean(y)) ** 2)

        if sst == 0:
            return 1.0
        return max(0.0, min(1.0, float(1.0 - (sse / sst))))

    def build_trend_dict(self, metric: str, data: list[tuple[int, float]]) -> dict:
        """Perform time-series analysis for a single metric and return a trend dictionary."""
        if not data:
            raise TrendCalculationError(f"Cannot calculate trend for metric '{metric}' with empty data.")

        try:
            # Sort visits chronologically before calculating the trend
            data.sort(key=lambda item: item[0])

            x = np.array([p[0] for p in data], dtype=float)
            y = np.array([p[1] for p in data], dtype=float)
        except (TypeError, ValueError, IndexError) as exc:
            raise TrendCalculationError(
                f"Malformed data points for metric '{metric}': {exc}"
            ) from exc

        baseline = float(y[0])
        latest = float(y[-1])

        # For a single visit
        if len(x) == 1:
            return {
                "metric": metric,
                "points": [{"session_number": int(x[0]), "value": baseline, "trend_value": None}],
                "statistics": {
                    "baseline_value": baseline,
                    "latest_value": latest,
                    "delta_absolute": None,
                    "delta_percent": None,
                    "slope_per_session": None,
                    "intercept": None,
                    "r_squared": None,
                },
            }

        # Guard against duplicate session numbers causing singular matrix in polyfit
        if len(np.unique(x)) < 2:
            raise TrendCalculationError(
                f"Cannot compute regression for metric '{metric}': at least two distinct session numbers are required."
            )

        try:
            slope, intercept = np.polyfit(x, y, 1)
            y_pred = slope * x + intercept
            r_squared = self._calculate_r_squared(y, y_pred)
        except Exception as exc:
            raise TrendCalculationError(
                f"Linear regression failed for metric '{metric}': {exc}"
            ) from exc

        points = [
            {"session_number": int(xi), "value": float(yi), "trend_value": float(y_hat)}
            for xi, yi, y_hat in zip(x, y, y_pred)
        ]

        delta_abs = latest - baseline
        delta_pct = (delta_abs / baseline * 100) if baseline != 0 else None

        return {
            "metric": metric,
            "points": points,
            "statistics": {
                "baseline_value": baseline,
                "latest_value": latest,
                "delta_absolute": float(delta_abs),
                "delta_percent": float(delta_pct) if delta_pct is not None else None,
                "slope_per_session": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r_squared),
            },
        }