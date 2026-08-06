from minsearch import Index

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

def build_text_index(documents):
    index = Index(
        text_fields=TEXT_FIELDS,
        keyword_fields=KEYWORD_FIELDS,
    )

    index.fit(documents)
    return index