import math
from .exceptions import InvalidVisitPayloadError, MissingSessionNumberError

class MetricsExtractor:

    @staticmethod
    def extract(visits: list[dict]) -> dict[str, list[tuple[int, float]]]:
        """Parse visits and group scalar metrics: {metric_name: [(session_num, value)]}."""
        if not isinstance(visits, list):
            raise InvalidVisitPayloadError(
                f"Expected 'visits' to be a list, got {type(visits).__name__}."
            )

        grouped_data = {}

        for idx, visit in enumerate(visits):
            if not isinstance(visit, dict):
                raise InvalidVisitPayloadError(
                    f"Visit at index {idx} must be a dict, got {type(visit).__name__}."
                )

            session_num = visit.get("session_number")
            if not isinstance(session_num, int) or isinstance(session_num, bool) or session_num < 1:
                raise MissingSessionNumberError(
                    f"Visit at index {idx} has an invalid or missing 'session_number': {session_num}."
                )

            biomarkers = visit.get("biomarkers")
            if biomarkers is None:
                biomarkers = {}
            elif not isinstance(biomarkers, dict):
                raise InvalidVisitPayloadError(
                    f"'biomarkers' in visit at index {idx} must be a dict, got {type(biomarkers).__name__}."
                )

            features = {}

            raw_features = biomarkers.get("raw_dsp_features")
            if isinstance(raw_features, dict):
                features.update(raw_features)

            inferred = biomarkers.get("inferred_indices")
            if isinstance(inferred, dict):
                features.update(inferred)

            # Keep only valid finite scalar numeric metrics, ignore booleans and nested objects
            for metric, val in features.items():
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    float_val = float(val)
                    if math.isnan(float_val) or math.isinf(float_val):
                        continue
                    if metric not in grouped_data:
                        grouped_data[metric] = []
                    grouped_data[metric].append((session_num, float_val))

        return grouped_data