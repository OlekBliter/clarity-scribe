import pytest
from src.systems.trends_tracking.dynamics_engine import calculate_dynamics
from src.schemas.s5_dynamics import S5In

def create_mock_biomarkers(f0_var: float):
    """Генерує мінімально валідний словник для S2Out згідно з контрактом"""
    return {
        "raw_dsp_features": {
            "f0_variability_sd": f0_var,
            "f0_mean_hz": 185.2,
            "jitter_percent": 1.45,
            "shimmer_percent": 4.12,
            "hnr_db": 16.8,
            "speech_rate_syllables_per_sec": 2.6,
            "pause_ratio": 0.32,
            "mean_latent_response_time_sec": 1.68
        },
        "inferred_indices": {
            "affect_flatness_flag": False,
            "vocal_jitter_percentile": 62.0,
            "psychomotor_retardation_index": 0.42,
            "intrasession_dynamics": {
                "f0_variability_change_percent": 240.0,
                "speech_rate_change_percent": 88.0,
                "pause_ratio_change_percent": -62.5,
                "trend_summary": "activation"
            }
        },
        "window_chunks": [
            {
                "window_index": 0,
                "time_range": "00:00-05:00",
                "f0_variability_sd": 7.2,
                "speech_rate_syllables_per_sec": 1.8,
                "pause_ratio": 0.48
            }
        ]
    }

def test_dynamics_single_visit():
    """Перевірка випадку одного візиту"""
    payload = {
        "visits": [
            {"session_number": 1, "biomarkers": create_mock_biomarkers(42.1)}
        ]
    }
    request = S5In.model_validate(payload)
    response = calculate_dynamics(request)
    
    # перший знайдений тренд
    f0_trend = next(t for t in response.trends if t.metric == "f0_variability_sd")
    
    assert len(f0_trend.points) == 1
    assert f0_trend.points[0].trend_value is None
    assert f0_trend.statistics.baseline_value == 42.1
    assert f0_trend.statistics.slope_per_session is None

def test_dynamics_multiple_visits():
    """Перевірка випадку для кількох візитів"""
    payload = {
        "visits": [
            {"session_number": 1, "biomarkers": create_mock_biomarkers(42.1)},
            {"session_number": 2, "biomarkers": create_mock_biomarkers(48.0)},
            {"session_number": 4, "biomarkers": create_mock_biomarkers(58.4)}
        ]
    }
    request = S5In.model_validate(payload)
    response = calculate_dynamics(request)
    
    f0_trend = next(t for t in response.trends if t.metric == "f0_variability_sd")
    
    assert len(f0_trend.points) == 3
    assert f0_trend.statistics.baseline_value == 42.1
    assert f0_trend.statistics.latest_value == 58.4
    
    # Перевірка на порожній slope і коректну delta
    assert f0_trend.statistics.slope_per_session is not None
    assert f0_trend.statistics.delta_absolute == pytest.approx(16.3, 0.01)
    
    # Валідатори Pydantic автоматично перевіряють R^2 та trend_value