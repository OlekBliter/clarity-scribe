from src.schemas.s5_dynamics import S5In, S5Out, S5Trend, S5Point, S5Statistics, S5Visit
import numpy as np


def _extract_numeric_metrics(visits: list[S5Visit]) -> dict[str, list[tuple[int, float]]]:
    """Парсить візити і групує скалярні метрики: {metric_name: [(session_num, value)]}."""
    grouped_data = {}

    for visit in visits:
        session_num = visit.session_number
        features = {}

        if hasattr(visit.biomarkers, 'raw_dsp_features') and visit.biomarkers.raw_dsp_features:
            features.update(visit.biomarkers.raw_dsp_features)
        if hasattr(visit.biomarkers, 'inferred_indices') and visit.biomarkers.inferred_indices:
            features.update(visit.biomarkers.inferred_indices)

        for metric, val in features.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                if metric not in grouped_data:
                    grouped_data[metric] = []
                grouped_data[metric].append((session_num, float(val)))

    return grouped_data

def _calculate_r_squared(y: np.ndarray, y_pred: np.ndarray) -> float:
    """Обчислює коефіцієнт детермінації R^2."""
    sse = np.sum((y - y_pred) ** 2)
    sst = np.sum((y - np.mean(y)) ** 2)

    if sst == 0:
        return 1.0
    
    return max(0.0, min(1.0, float(1.0 - (sse / sst))))

def _build_trend(metric: str, data: list[tuple[int, float]]) -> S5Trend:
    """Виконує time-series аналіз для однієї метрики та формує S5Trend."""
    x = np.array([p[0] for p in data])
    y = np.array([p[1] for p in data])
    
    baseline = float(y[0])
    latest = float(y[-1])
    
    # для 1 візиту
    if len(x) == 1:
        points = [S5Point(session_number=int(x[0]), value=baseline, trend_value=None)]
        stats = S5Statistics(
            baseline_value=baseline, latest_value=latest,
            delta_absolute=None, delta_percent=None,
            slope_per_session=None, intercept=None, r_squared=None
        )
        return S5Trend(metric=metric, points=points, statistics=stats)
        
    # для кількох візитів
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    r_squared = _calculate_r_squared(y, y_pred)
    
    points = [
        S5Point(session_number=int(xi), value=float(yi), trend_value=float(y_hat))
        for xi, yi, y_hat in zip(x, y, y_pred)
    ]
    
    delta_abs = latest - baseline
    delta_pct = (delta_abs / baseline * 100) if baseline != 0 else None
    
    stats = S5Statistics(
        baseline_value=baseline,
        latest_value=latest,
        delta_absolute=float(delta_abs),
        delta_percent=float(delta_pct) if delta_pct is not None else None,
        slope_per_session=float(slope),
        intercept=float(intercept),
        r_squared=float(r_squared)
    )
    
    return S5Trend(metric=metric, points=points, statistics=stats)

def calculate_dynamics(request: S5In) -> S5Out:
    """
    Головна точка входу для Оркестратора.
    Приймає контракт S5In, проганяє time-series аналіз і віддає S5Out.
    """
    grouped_data = _extract_numeric_metrics(request.visits)
    trends = [_build_trend(metric, data) for metric, data in grouped_data.items()]
    
    return S5Out(trends=trends)