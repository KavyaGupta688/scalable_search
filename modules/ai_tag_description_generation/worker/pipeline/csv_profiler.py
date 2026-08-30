# worker/pipeline/csv_profiler.py
"""
Layer 5 - CSV Profiler.

Profiles a CSV's structure (columns, inferred types, null rates, sample
values) rather than treating it as free text. This structured profile is
what downstream tagging/captioning stages describe, instead of trying to
run vision/language models on raw tabular data.
"""

from dataclasses import dataclass, field

import pandas as pd


MAX_SAMPLE_ROWS = 5
MAX_UNIQUE_VALUES_TO_LIST = 10  # for likely-categorical columns


@dataclass
class ColumnProfile:
    name: str
    inferred_type: str          # "numeric" | "categorical" | "text" | "datetime" | "boolean"
    null_rate: float
    unique_count: int
    sample_values: list


@dataclass
class ProcessedCSV:
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    sample_rows: list[dict]
    known_metadata_columns: list[str]  # columns matching expected ingestion fields (title/category/tags)


# Column names the Ingestion module is known to sometimes provide directly -
# if present, downstream stages can use these as strong signal rather than
# inferring tags/description from scratch.
KNOWN_METADATA_COLUMN_NAMES = {"title", "category", "tags", "description", "label"}


def process_csv(file_path: str) -> ProcessedCSV:
    df = pd.read_csv(file_path)

    columns = [_profile_column(df, col) for col in df.columns]
    known_metadata_columns = [
        col for col in df.columns if col.strip().lower() in KNOWN_METADATA_COLUMN_NAMES
    ]

    sample_rows = df.head(MAX_SAMPLE_ROWS).to_dict(orient="records")

    return ProcessedCSV(
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        sample_rows=sample_rows,
        known_metadata_columns=known_metadata_columns,
    )


def _profile_column(df: pd.DataFrame, col: str) -> ColumnProfile:
    series = df[col]
    null_rate = float(series.isna().mean())
    unique_count = int(series.nunique())
    inferred_type = _infer_type(series)

    non_null = series.dropna()
    if inferred_type == "categorical" and unique_count <= MAX_UNIQUE_VALUES_TO_LIST:
        samples = non_null.unique().tolist()[:MAX_UNIQUE_VALUES_TO_LIST]
    else:
        samples = non_null.head(3).tolist()

    return ColumnProfile(
        name=col,
        inferred_type=inferred_type,
        null_rate=null_rate,
        unique_count=unique_count,
        sample_values=samples,
    )


def _infer_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    # Try datetime parsing on object columns - CSVs almost always load
    # dates as strings, so is_datetime64_any_dtype alone misses most of them.
    non_null = series.dropna()
    if len(non_null) > 0:
        try:
            pd.to_datetime(non_null.head(20), errors="raise")
            return "datetime"
        except (ValueError, TypeError):
            pass

    # Heuristic: low cardinality relative to row count suggests a
    # categorical column (e.g. "status", "category") rather than free text.
    if len(series) > 0 and series.nunique() / len(series) < 0.5:
        return "categorical"

    return "text"


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sample.csv"
    result = process_csv(path)

    print(f"Rows: {result.row_count}, Columns: {result.column_count}")
    print(f"Known metadata columns found: {result.known_metadata_columns}")
    print()
    for col in result.columns:
        print(f"  {col.name:20s} type={col.inferred_type:12s} nulls={col.null_rate:.1%} unique={col.unique_count} samples={col.sample_values}")
    print()
    print("Sample rows:")
    for row in result.sample_rows[:2]:
        print(f"  {row}")