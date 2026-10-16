import pytest
from src.systems.longitudinal.metrics_extractor import MetricsExtractor
from src.systems.longitudinal.trend_calculator import TrendCalculator
from src.systems.longitudinal.dynamics_service import DynamicsService
from src.schemas.contracts import S5Out
from src.systems.longitudinal.exceptions import (
    InvalidVisitPayloadError,
    MissingSessionNumberError,
    TrendCalculationError,
)

extractor = MetricsExtractor()
calculator = TrendCalculator()

service = DynamicsService(extractor=extractor, calculator=calculator)

def create_mock_biomarkers(f0_var: float):
    """Create a minimal valid biomarker payload for the S2Out contract."""
    return {
        "raw_dsp_features": {
            "f0_variability_sd": f0_var,
            "f0_mean_hz": 185.2,
            "jitter_percent": 1.45,
            "shimmer_percent": 4.12,
            "hnr_db": 16.8,
            "speech_rate_syllables_per_sec": 2.6,
            "pause_ratio": 0.32,
            "mean_latent_response_time_sec": 1.68,
        },
        "inferred_indices": {
            "affect_flatness_flag": False,
            "vocal_jitter_percentile": 62.0,
            "psychomotor_retardation_index": 0.42,
            "intrasession_dynamics": {
                "f0_variability_change_percent": 240.0,
                "speech_rate_change_percent": 88.0,
                "pause_ratio_change_percent": -62.5,
                "trend_summary": "activation",
            },
        },
        "window_chunks": [
            {
                "window_index": 0,
                "time_range": "00:00-05:00",
                "f0_variability_sd": 7.2,
                "speech_rate_syllables_per_sec": 1.8,
                "pause_ratio": 0.48,
            }
        ],
    }


def test_dynamics_single_visit():
    """Check the single-visit case."""
    visits_payload = [{"session_number": 1, "biomarkers": create_mock_biomarkers(42.1)}]

    out_dict = service.calculate(visits=visits_payload)
    response = S5Out.model_validate(out_dict)
    f0_trend = next(t for t in response.trends if t.metric == "f0_variability_sd")

    assert len(f0_trend.points) == 1
    assert f0_trend.points[0].trend_value is None
    assert f0_trend.statistics.baseline_value == 42.1
    assert f0_trend.statistics.slope_per_session is None


def test_dynamics_multiple_visits():
    """Check the multi-visit case."""
    visits_payload = [
        {"session_number": 1, "biomarkers": create_mock_biomarkers(42.1)},
        {"session_number": 2, "biomarkers": create_mock_biomarkers(48.0)},
        {"session_number": 4, "biomarkers": create_mock_biomarkers(58.4)},
    ]

    out_dict = service.calculate(visits=visits_payload)
    response = S5Out.model_validate(out_dict)

    f0_trend = next(t for t in response.trends if t.metric == "f0_variability_sd")
    assert len(f0_trend.points) == 3
    assert f0_trend.statistics.baseline_value == 42.1
    assert f0_trend.statistics.latest_value == 58.4
    assert f0_trend.statistics.slope_per_session is not None
    assert f0_trend.statistics.delta_absolute == pytest.approx(16.3, 0.01)


def test_invalid_visits_payload_type():
    """Ensure non-list payload raises InvalidVisitPayloadError."""
    with pytest.raises(InvalidVisitPayloadError):
        service.calculate(visits="invalid_payload")  # type: ignore


def test_missing_session_number():
    """Ensure missing session_number raises MissingSessionNumberError."""
    visits_payload = [{"biomarkers": create_mock_biomarkers(42.1)}]
    with pytest.raises(MissingSessionNumberError):
        service.calculate(visits=visits_payload)


def test_duplicate_session_numbers_error():
    """Ensure identical session numbers raise TrendCalculationError instead of numpy crash."""
    visits_payload = [
        {"session_number": 1, "biomarkers": create_mock_biomarkers(42.1)},
        {"session_number": 1, "biomarkers": create_mock_biomarkers(48.0)},
    ]
    with pytest.raises(TrendCalculationError):
        service.calculate(visits=visits_payload)