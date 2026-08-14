"""Fetch a small picture for every herb in the knowledge base.

Looks up each herb's botanical name (falling back to its English name) on
Wikipedia and records the article's thumbnail URL in data/herb_images.csv.
Uses the MediaWiki batch API (50 titles per request) to stay well inside
Wikipedia's rate limits.

The output file is a presentation-layer sidecar: nothing in the search
indexes, embeddings, or evaluation depends on it.

Usage:
    python fetch_herb_images.py
"""

import time
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KB_CSV = PROJECT_ROOT / "data" / "knowledge_base.csv"
IMAGES_CSV = PROJECT_ROOT / "data" / "herb_images.csv"

API_URL = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "natural-remedy-consultant (educational project)"}
THUMB_SIZE = 240
BATCH_SIZE = 50


def batch_lookup(titles):
    """Return {title: {image_url, page_url}} for titles that have a thumbnail."""
    params = {
        "action": "query",
        "format": "json",
        "titles": "|".join(titles),
        "prop": "pageimages|info",
        "piprop": "thumbnail",
        "pithumbsize": THUMB_SIZE,
        "inprop": "url",
        "redirects": 1,
    }

    for attempt in range(3):
        response = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
        if response.status_code == 429:
            time.sleep(int(response.headers.get("retry-after", 15)))
            continue
        response.raise_for_status()
        break

    data = response.json()["query"]

    # Wikipedia may normalize ("Ginkgo_biloba" -> "Ginkgo biloba") and
    # redirect ("Lavender" -> "Lavandula") titles; follow both mappings
    mapping = {}
    for entry in data.get("normalized", []) + data.get("redirects", []):
        mapping[entry["from"]] = entry["to"]

    def resolve(title):
        seen = set()
        while title in mapping and title not in seen:
            seen.add(title)
            title = mapping[title]
        return title

    by_title = {}
    for page in data["pages"].values():
        if "thumbnail" in page:
            by_title[page["title"]] = {
                "image_url": page["thumbnail"]["source"],
                "page_url": page.get("fullurl", ""),
            }

    return {title: by_title.get(resolve(title)) for title in titles}


def lookup_all(titles):
    results = {}
    for i in range(0, len(titles), BATCH_SIZE):
        results.update(batch_lookup(titles[i : i + BATCH_SIZE]))
        time.sleep(1)
    return results


def fetch_all():
    df = pd.read_csv(KB_CSV)
    herbs = df[["herb_id", "herb_name_en", "botanical_name"]].drop_duplicates("herb_id")

    by_botanical = lookup_all(list(herbs["botanical_name"]))

    fallbacks = [
        h.herb_name_en for h in herbs.itertuples(index=False)
        if not by_botanical.get(h.botanical_name)
    ]
    by_english = lookup_all(fallbacks) if fallbacks else {}

    rows = []
    misses = []

    for herb in herbs.itertuples(index=False):
        result = by_botanical.get(herb.botanical_name) or by_english.get(herb.herb_name_en)
        if result:
            rows.append({
                "herb_id": herb.herb_id,
                "herb_name_en": herb.herb_name_en,
                "botanical_name": herb.botanical_name,
                **result,
            })
        else:
            misses.append(herb.herb_name_en)

    pd.DataFrame(rows).to_csv(IMAGES_CSV, index=False)

    print(f"Saved {len(rows)}/{len(herbs)} herb images to {IMAGES_CSV}")
    if misses:
        print("No image found for:", ", ".join(misses))


if __name__ == "__main__":
    fetch_all()
