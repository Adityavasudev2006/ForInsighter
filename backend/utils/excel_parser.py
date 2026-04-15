from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

MAX_TEXT_ROWS_PER_SHEET = 250
MAX_TEXT_COLS = 30

def _clean_value(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _detect_inconsistent_formats(series: pd.Series, col_name: str) -> list[str]:
    values = [_clean_value(v) for v in series.dropna().head(300).tolist()]
    if len(values) < 5:
        return []
    date_like = [v for v in values if re.search(r"\d+[/-]\d+[/-]\d+", v)]
    if len(date_like) >= 3:
        slash = sum(1 for v in date_like if "/" in v)
        dash = sum(1 for v in date_like if "-" in v)
        if slash and dash:
            return [f"{col_name}: mixed date separators detected"]
    return []


def _series_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    numeric = pd.to_numeric(non_null, errors="coerce")
    numeric_ratio = float(numeric.notna().mean())
    if numeric_ratio > 0.95:
        return "numeric"
    dt = pd.to_datetime(non_null, errors="coerce")
    dt_ratio = float(dt.notna().mean())
    if dt_ratio > 0.95:
        return "datetime"
    if 0.3 < numeric_ratio <= 0.95:
        return "mixed(numeric/text)"
    return "categorical"


def _build_tabular_profile(df: pd.DataFrame, file_size: int, sheet_count: int) -> dict:
    column_types: dict[str, str] = {}
    missing_values_per_column: dict[str, int] = {}
    unique_values_per_column: dict[str, int] = {}
    numerical_stats: dict[str, dict] = {}
    categorical_stats: dict[str, dict] = {}
    inconsistent_formats: list[str] = []
    invalid_values: list[str] = []

    for col in df.columns:
        series = df[col]
        col_name = str(col)
        inferred = _series_type(series)
        column_types[col_name] = inferred
        missing_values_per_column[col_name] = int(series.isna().sum())
        unique_values_per_column[col_name] = int(series.nunique(dropna=True))
        inconsistent_formats.extend(_detect_inconsistent_formats(series, col_name))

        if inferred in {"numeric", "mixed(numeric/text)"}:
            num = pd.to_numeric(series, errors="coerce").dropna()
            if not num.empty:
                q1 = float(num.quantile(0.25))
                q3 = float(num.quantile(0.75))
                iqr = q3 - q1
                outlier_mask = (num < (q1 - 1.5 * iqr)) | (num > (q3 + 1.5 * iqr))
                numerical_stats[col_name] = {
                    "min": float(num.min()),
                    "max": float(num.max()),
                    "median": float(num.median()),
                    "variance": float(num.var(ddof=1)) if len(num) > 1 else 0.0,
                    "std": float(num.std(ddof=1)) if len(num) > 1 else 0.0,
                    "mode": float(num.mode().iloc[0]) if not num.mode().empty else None,
                    "outliers": int(outlier_mask.sum()),
                }
                if "age" in col_name.lower() and (num < 0).any():
                    invalid_values.append(f"{col_name}: contains negative values")
        else:
            vals = series.dropna().astype(str).str.strip()
            mode_val = vals.mode().iloc[0] if not vals.mode().empty else None
            categorical_stats[col_name] = {
                "mode": mode_val,
                "unique_count": int(vals.nunique()),
            }

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [str(c) for c in df.columns],
        "column_types": column_types,
        "file_size_bytes": int(file_size),
        "sheet_count": int(sheet_count),
        "missing_values_per_column": missing_values_per_column,
        "missing_values_total": int(sum(missing_values_per_column.values())),
        "unique_values_per_column": unique_values_per_column,
        "numerical_stats": numerical_stats,
        "categorical_stats": categorical_stats,
        "duplicate_rows": int(df.duplicated().sum()),
        "inconsistent_formats": inconsistent_formats,
        "invalid_values": invalid_values,
    }


def parse_excel(file_path: str) -> dict:
    output = {"sheets": [], "full_text": "", "tabular": None}
    full_parts: list[str] = []
    path = Path(file_path)
    suffix = path.suffix.lower()
    file_size = path.stat().st_size if path.exists() else 0
    try:
        frames: list[tuple[str, pd.DataFrame]] = []
        if suffix == ".csv":
            # Fast CSV loading with type inference off for speed/stability.
            df = pd.read_csv(file_path, low_memory=False, engine="c")
            frames.append(("Sheet1", df))
        else:
            # .xls frequently requires xlrd; try default first, then xlrd fallback.
            try:
                xls = pd.ExcelFile(file_path)
            except Exception:
                xls = pd.ExcelFile(file_path, engine="xlrd")
            for sheet_name in xls.sheet_names:
                try:
                    frames.append((sheet_name, xls.parse(sheet_name=sheet_name)))
                except Exception:
                    continue

        merged_df_parts: list[pd.DataFrame] = []
        for sheet_name, df in frames:
            if df is None:
                continue
            df = df.copy()
            df.columns = [str(c).strip() or f"column_{i+1}" for i, c in enumerate(df.columns)]
            df = df.dropna(how="all")
            if df.empty:
                output["sheets"].append({"sheet_name": sheet_name, "text": "", "rows": []})
                continue
            merged_df_parts.append(df)
            # Keep LLM context compact to avoid slow embedding/summary on huge tables.
            text_lines: list[str] = []
            preview_df = df.head(MAX_TEXT_ROWS_PER_SHEET).iloc[:, :MAX_TEXT_COLS]
            for idx, row in preview_df.iterrows():
                row_map = [f"{col}: {_clean_value(row[col])}" for col in preview_df.columns]
                text_lines.append(f"row_{int(idx)+1} | " + " | ".join(row_map))
            sheet_text = "\n".join(text_lines).strip()
            output["sheets"].append({"sheet_name": sheet_name, "text": sheet_text, "rows": []})
            if sheet_text:
                full_parts.append(f"Sheet: {sheet_name}\n{sheet_text}")

        output["full_text"] = "\n\n".join(full_parts).strip()
        if merged_df_parts:
            merged = pd.concat(merged_df_parts, ignore_index=True, sort=False)
            profile = _build_tabular_profile(merged, file_size=file_size, sheet_count=max(1, len(frames)))
            profile["preview_rows_per_sheet"] = MAX_TEXT_ROWS_PER_SHEET
            output["tabular"] = profile
            # Rich but concise LLM context to prevent "row-dump" summaries.
            summary_lines = [
                f"Dataset overview: rows={profile['row_count']}, columns={profile['column_count']}, sheets={profile['sheet_count']}.",
                f"Columns: {', '.join(profile['columns'][:30])}",
                f"Column types: {', '.join([f'{k}={v}' for k, v in list(profile['column_types'].items())[:30]])}",
                f"Missing values total: {profile['missing_values_total']}. Duplicate rows: {profile['duplicate_rows']}.",
            ]
            if not output["full_text"]:
                output["full_text"] = "\n".join(summary_lines)
            else:
                output["full_text"] = "\n".join(summary_lines) + "\n\n" + output["full_text"]
        return output
    except Exception:
        return output
