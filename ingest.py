from minsearch import Index
import pandas as pd

TEXT_FIELDS = [
    "condition_normalized",
    "condition_or_use_case",
    "symptom_tags",
    "herb_name_en",
    "herb_name_zh",
    "pinyin",
    "botanical_name",
    "traditional_pattern",
    "traditional_role",
    "remedy_summary",
    "modern_evidence_summary",
    "preparation_example",
    "adverse_effects",
    "contraindications_and_cautions",
    "key_drug_interactions",
]

KEYWORD_FIELDS = [
    "record_id",
    "herb_id",
    "record_type",
    "indication_system",
    "evidence_level",
    "preparation_type",
    "needs_expert_review",
    "do_not_generate_dose",
]


def load_data():
    df = pd.read_csv("natural_remedies.csv")

    # Remove an old CSV index column, if present
    df = df.drop(columns=["index"], errors="ignore")

    # Minsearch text fields should not contain NaN values
    df = df.fillna("")

    return df.to_dict(orient="records")

def build_index(documents):
    index = Index(
        text_fields=TEXT_FIELDS,
        keyword_fields=KEYWORD_FIELDS,
    )

    index.fit(documents)

    return index