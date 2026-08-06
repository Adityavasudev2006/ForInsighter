from __future__ import annotations


class ChartService:
    def build_charts(self, profile: dict | None) -> list[dict]:
        if not isinstance(profile, dict):
            return []

        charts: list[dict] = []
        missing = profile.get("missing_values_per_column") or {}
        uniques = profile.get("unique_values_per_column") or {}
        numerical = profile.get("numerical_stats") or {}
        categorical = profile.get("categorical_stats") or {}

        if missing:
            charts.append(
                {
                    "id": "missing_by_column",
                    "title": "Missing Values by Column",
                    "type": "bar",
                    "data": [{"name": k, "value": v} for k, v in missing.items()],
                    "xKey": "name",
                    "yKey": "value",
                }
            )
        if uniques:
            charts.append(
                {
                    "id": "unique_by_column",
                    "title": "Unique Values by Column",
                    "type": "bar",
                    "data": [{"name": k, "value": v} for k, v in uniques.items()],
                    "xKey": "name",
                    "yKey": "value",
                }
            )
        if numerical:
            charts.append(
                {
                    "id": "numeric_minmax",
                    "title": "Numeric Min/Max",
                    "type": "line",
                    "data": [
                        {"name": col, "min": vals.get("min"), "max": vals.get("max")}
                        for col, vals in numerical.items()
                    ],
                    "xKey": "name",
                    "series": ["min", "max"],
                }
            )
            charts.append(
                {
                    "id": "numeric_variance",
                    "title": "Variance by Numeric Column",
                    "type": "bar",
                    "data": [{"name": col, "value": vals.get("variance", 0)} for col, vals in numerical.items()],
                    "xKey": "name",
                    "yKey": "value",
                }
            )
            charts.append(
                {
                    "id": "numeric_outliers",
                    "title": "Outliers by Numeric Column",
                    "type": "bar",
                    "data": [{"name": col, "value": vals.get("outliers", 0)} for col, vals in numerical.items()],
                    "xKey": "name",
                    "yKey": "value",
                }
            )
        if categorical:
            charts.append(
                {
                    "id": "categorical_unique_counts",
                    "title": "Categorical Unique Counts",
                    "type": "bar",
                    "data": [{"name": col, "value": vals.get("unique_count", 0)} for col, vals in categorical.items()],
                    "xKey": "name",
                    "yKey": "value",
                }
            )

        quality_data = [
            {"name": "rows", "value": profile.get("row_count", 0)},
            {"name": "columns", "value": profile.get("column_count", 0)},
            {"name": "duplicates", "value": profile.get("duplicate_rows", 0)},
            {"name": "missing_total", "value": profile.get("missing_values_total", 0)},
        ]
        charts.append(
            {
                "id": "dataset_quality_overview",
                "title": "Dataset Quality Overview",
                "type": "bar",
                "data": quality_data,
                "xKey": "name",
                "yKey": "value",
            }
        )
        return charts[:10]
