"""Automated ingestion pipeline for the natural remedy knowledge base.

Orchestrated with Prefect: extract -> validate -> transform -> load -> smoke test.
Reads the raw dataset, checks it against the schema the consultant app expects,
and publishes the processed knowledge base file consumed by the app.

Usage:
    python auto_data_ingestion.py
"""

from pathlib import Path

import pandas as pd
from prefect import flow, task, get_run_logger

from ingest import TEXT_FIELDS, KEYWORD_FIELDS, build_index

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "data" / "natural_remedies.csv"
KB_CSV = PROJECT_ROOT / "data" / "knowledge_base.csv"

REQUIRED_COLUMNS = set(TEXT_FIELDS) | set(KEYWORD_FIELDS)


@task(retries=2, retry_delay_seconds=5)
def extract(csv_path: Path) -> pd.DataFrame:
    logger = get_run_logger()
    df = pd.read_csv(csv_path)
    logger.info("Extracted %d rows from %s", len(df), csv_path.name)
    return df


@task
def validate(df: pd.DataFrame) -> pd.DataFrame:
    logger = get_run_logger()

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    if df["record_id"].isna().any():
        raise ValueError("Found records without a record_id")

    duplicates = df["record_id"].duplicated()
    if duplicates.any():
        logger.warning("Dropping %d duplicate record_ids", int(duplicates.sum()))
        df = df[~duplicates]

    logger.info("Validated %d records", len(df))
    return df


@task
def transform(df: pd.DataFrame) -> pd.DataFrame:
    logger = get_run_logger()

    # Remove an old CSV index column, if present
    df = df.drop(columns=["index"], errors="ignore")

    # Minsearch text fields should not contain NaN values
    df = df.fillna("")

    logger.info("Transformed dataset: %d rows, %d columns", *df.shape)
    return df


@task
def load(df: pd.DataFrame, kb_path: Path) -> Path:
    logger = get_run_logger()

    kb_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(kb_path, index=False)

    logger.info("Knowledge base written to %s", kb_path)
    return kb_path


@task
def smoke_test(kb_path: Path) -> None:
    logger = get_run_logger()

    documents = pd.read_csv(kb_path).fillna("").to_dict(orient="records")
    index = build_index(documents)

    results = index.search("ginger for nausea", num_results=3)
    if not results:
        raise RuntimeError("Smoke test failed: index returned no search results")

    logger.info(
        "Smoke test passed: %d records indexed, top hit %s (%s)",
        len(documents),
        results[0]["record_id"],
        results[0]["herb_name_en"],
    )


@flow(name="natural-remedy-kb-ingestion")
def ingest_knowledge_base(raw_csv: Path = RAW_CSV, kb_csv: Path = KB_CSV) -> Path:
    df = extract(raw_csv)
    df = validate(df)
    df = transform(df)
    kb_path = load(df, kb_csv)
    smoke_test(kb_path)
    return kb_path


if __name__ == "__main__":
    ingest_knowledge_base()
