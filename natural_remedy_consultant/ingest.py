from pathlib import Path

import numpy as np
import pandas as pd
from minsearch import Index, VectorSearch

from embedder import Embedder

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KB_CSV = PROJECT_ROOT / "data" / "knowledge_base.csv"
RAW_CSV = PROJECT_ROOT / "data" / "natural_remedies.csv"
EMBEDDINGS_CACHE = PROJECT_ROOT / "data" / "embeddings.npy"

# Record fields the app relies on, used for validation and context building.
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


def prepare_documents(df):
    # Remove an old CSV index column, if present
    df = df.drop(columns=["index"], errors="ignore")

    # Minsearch text fields should not contain NaN values
    df = df.fillna("")

    # The retrieval evaluation showed searching over the pre-built
    # retrieval_text summary outperforms searching individual fields
    df["content"] = df["retrieval_text"]

    return df.to_dict(orient="records")


def load_data():
    # Prefer the knowledge base published by auto_data_ingestion.py,
    # fall back to the raw dataset if the pipeline has not been run yet
    csv_path = KB_CSV if KB_CSV.exists() else RAW_CSV

    return prepare_documents(pd.read_csv(csv_path))


def embed_documents(documents, embedder, cache_path=EMBEDDINGS_CACHE, batch_size=32):
    if cache_path.exists():
        cache_fresh = (
            not KB_CSV.exists()
            or cache_path.stat().st_mtime >= KB_CSV.stat().st_mtime
        )
        X = np.load(cache_path)
        if X.shape[0] == len(documents) and cache_fresh:
            return X

    texts = [doc["content"] for doc in documents]
    batches = [
        embedder.encode_batch(texts[i : i + batch_size])
        for i in range(0, len(texts), batch_size)
    ]
    X = np.vstack(batches)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, X)

    return X


class HybridSearcher:
    """Text + vector search fused with Reciprocal Rank Fusion.

    This is the best-performing retriever from the retrieval evaluation
    (hit_rate 0.963, MRR 0.631 on the ground-truth test set).
    """

    def __init__(self, text_index, vector_index, embedder, k=60, num_candidates=10):
        self.text_index = text_index
        self.vector_index = vector_index
        self.embedder = embedder
        self.k = k
        self.num_candidates = num_candidates

    def search(self, query, num_results=5):
        text_results = self.text_index.search(
            query, num_results=self.num_candidates
        )
        vector_results = self.vector_index.search(
            self.embedder.encode(query), num_results=self.num_candidates
        )

        scores = {}
        docs = {}
        for results in (text_results, vector_results):
            for rank, doc in enumerate(results):
                key = doc["record_id"]
                scores[key] = scores.get(key, 0) + 1 / (self.k + rank)
                docs[key] = doc

        ranked = sorted(scores, key=scores.get, reverse=True)
        return [docs[key] for key in ranked[:num_results]]


def build_index(documents):
    text_index = Index(text_fields=["content"])
    text_index.fit(documents)

    embedder = Embedder()
    X = embed_documents(documents, embedder)

    vector_index = VectorSearch(keyword_fields=["record_id"])
    vector_index.fit(X, documents)

    return HybridSearcher(text_index, vector_index, embedder)
