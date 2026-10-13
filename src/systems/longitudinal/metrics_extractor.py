class MetricsExtractor:

    @staticmethod
    def extract(visits: list[dict]) -> dict[str, list[tuple[int, float]]]:
        """Parse visits and group scalar metrics: {metric_name: [(session_num, value)]}."""
        grouped_data = {}

        for visit in visits:
            session_num = visit.get("session_number")
            biomarkers = visit.get("biomarkers", {})
            features = {}

            raw_features = biomarkers.get("raw_dsp_features")
            if isinstance(raw_features, dict):
                features.update(raw_features)

            inferred = biomarkers.get("inferred_indicies")
            if isinstance(inferred, dict):
                features.update(inferred)

            # Keep only scalar numeric metrics, ignore booleans and nested objects
            for metric, val in features.items():
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    if metric not in grouped_data:
                        grouped_data[metric] = []
                    grouped_data[metric].append((session_num, float(val)))

        return grouped_data