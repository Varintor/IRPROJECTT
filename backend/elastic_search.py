from pathlib import Path

import numpy as np
from elasticsearch import Elasticsearch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from data_loader import get_documents

# ใช้ index "recipes" ที่มีอยู่ (ไม่ได้สร้างจาก notebook)
INDEX_NAME = "recipes"

es = Elasticsearch(
    "http://localhost:9200",
)


# LOAD CUSTOM TF-IDF INDEX (lazy load - don't load at import time!)
_documents = None
_tfidf_model = None
_tfidf_matrix = None

def _get_search_index():
    """Lazy load the search index"""
    global _documents, _tfidf_model, _tfidf_matrix
    if _documents is None:
        print("Loading search index (lazy load)...")
        _documents = get_documents()

        # ✅ FIX: Use pre-loaded TF-IDF model instead of creating new one (saves memory!)
        try:
            import pickle
            print("Loading pre-trained TF-IDF model...")
            with open('resources/tfidf.pkl', 'rb') as f:
                _tfidf_model = pickle.load(f)
            print(f"✅ TF-IDF model loaded (vocab size: {len(_tfidf_model.vocabulary_)})")

            # Load pre-computed TF-IDF matrix
            with open('resources/tfidf_matrix.pkl', 'rb') as f:
                _tfidf_matrix = pickle.load(f)
            print(f"✅ TF-IDF matrix loaded (shape: {_tfidf_matrix.shape})")

        except Exception as e:
            print(f"⚠️  Could not load pre-trained TF-IDF: {e}")
            print("Falling back to creating new TF-IDF vectorizer...")
            _tfidf_model = TfidfVectorizer(ngram_range=(1, 1), max_features=50000)  # Limit vocab size
            _tfidf_matrix = _tfidf_model.fit_transform(_documents["processed_text"])

        print("Search index loaded!")
    return _documents, _tfidf_model, _tfidf_matrix


# HELPERS
def minmax_normalize(scores):
    if len(scores) == 0:
        return []

    mn = min(scores)
    mx = max(scores)

    if mx == mn:
        return [1.0 for _ in scores]

    return [(s - mn) / (mx - mn) for s in scores]


def elastic_retrieve(query, top_k=100):
    """
    ใช้ search logic เดียวกับ notebook ES_PJ.ipynb
    - Multi-match พร้อม field weights
    - Cross-fields type + AND operator
    - Spell suggestion
    - Highlight
    """
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": [
                    "name^5",           # ชื่อสูตร x5 (สำคัญที่สุด)
                    "ingredient_parts^2",  # วัตถุดิบ x2
                    "instructions"  # วิธีทำ x1
                ],
                "type": "cross_fields",      # ค้นหาข้าม fields
                "operator": "and"            # ต้อง match ทุกคำ
            }
        },
        "suggest": {
            "text": query,
            "spell_suggest": {
                "phrase": {
                    "field": "name",
                    "size": 1,
                    "gram_size": 3,
                    "direct_generator": [
                        {
                            "field": "name",
                            "suggest_mode": "always"
                        }
                    ]
                }
            }
        },
        "highlight": {
            "fields": {
                "instructions": {
                    "pre_tags": ["**"],
                    "post_tags": ["**"],
                    "fragment_size": 100,
                    "number_of_fragments": 1
                }
            }
        }
    }

    res = es.search(
        index=INDEX_NAME,
        body=body,
    )

    return res


def tfidf_search_scores(query):
    """
    คำนวณ custom TF-IDF cosine similarity กับทุก document
    แล้วคืนเป็น dict: recipe_id -> score

    ⚠️  TEMPORARY FIX: Return empty scores to avoid memory error
    TODO: Fix TF-IDF matrix loading issue
    """
    # ⚠️ TEMPORARY: Return empty dict (use Elasticsearch scores only)
    # This avoids the 276 MiB memory allocation error
    print("⚠️  Using Elasticsearch-only mode (TF-IDF disabled due to memory)")
    return {}


# HYBRID SEARCH
def search(query, top_k=5, candidate_k=100, alpha=0.5):
    """
    alpha = น้ำหนักของ Elasticsearch score
    (1 - alpha) = น้ำหนักของ custom TF-IDF score

    ใช้ search logic เดียวกับ notebook ES_PJ.ipynb
    """
    # Lazy load search index
    documents, tfidf_vectorizer, X_tfidf = _get_search_index()

    # 1) ดึง candidate จาก Elasticsearch ก่อน
    es_response = elastic_retrieve(query, top_k=candidate_k)
    es_hits = es_response["hits"]["hits"]

    # ดึง spell suggestions (ถ้ามี)
    suggestions = []
    if "suggest" in es_response and es_response["suggest"]["spell_suggest"][0]["options"]:
        for option in es_response["suggest"]["spell_suggest"][0]["options"]:
            suggestions.append(option["text"])

    # 2) คำนวณ TF-IDF score custom
    tfidf_score_map = tfidf_search_scores(query)

    # Normalize scores
    max_score = es_response["hits"]["max_score"]
    if not max_score:
        max_score = 1.0

    temp_results = []

    for hit in es_hits:
        src = hit["_source"]
        recipe_id = int(src["recipe_id"])
        es_score = float(hit["_score"] / max_score)  # Normalize to 0-1
        tfidf_score = float(tfidf_score_map.get(recipe_id, 0.0))

        # ดึง highlight (ถ้ามี)
        highlight = ""
        if "highlight" in hit and "instructions" in hit["highlight"]:
            highlight = hit["highlight"]["instructions"][0]

        # ✅ FIX: ดึงทุกข้อมูลจาก Pickle DataFrame (Single Source of Truth)
        # Elasticsearch ใช้แค่ search, ดึง details จาก DataFrame
        total_time = "30 min"
        description = ""
        name = ""
        category = ""
        images = ""
        ingredient_parts = ""
        instructions = ""
        aggregated_rating = 0.0
        review_count = 0

        try:
            # Query documents DataFrame อย่างปลอดภัย
            doc_rows = documents[documents['recipe_id'] == recipe_id]
            if len(doc_rows) > 0:
                doc_row = doc_rows.iloc[0]
                total_time = str(doc_row.get('total_time', '30 min')) if doc_row.get('total_time') else "30 min"
                description = str(doc_row.get('processed_text', ''))[:200] if doc_row.get('processed_text') else ""

                # ✅ ดึงทุก fields จาก Pickle DataFrame
                name = str(doc_row.get('name', ''))
                category = str(doc_row.get('category', ''))
                images = str(doc_row.get('images', ''))
                ingredient_parts = str(doc_row.get('ingredient_parts', ''))
                instructions = str(doc_row.get('instructions', ''))

                # ✅ Rating fields จาก Pickle DataFrame (ไม่ใช่ ES!)
                import pandas as pd
                if pd.notna(doc_row.get('aggregated_rating')):
                    aggregated_rating = float(doc_row['aggregated_rating'])
                if pd.notna(doc_row.get('review_count')):
                    review_count = int(doc_row['review_count'])

        except Exception as e:
            print(f"Warning: Error fetching data for recipe {recipe_id}: {e}")
            # Fallback ถ้า error ใช้ค่าจาก Elasticsearch (ถ้ามี)
            name = src.get("name", "")
            category = src.get("category", "")
            images = src.get("images", "")
            ingredient_parts = src.get("ingredient_parts", "")
            instructions = src.get("instructions", "")

        temp_results.append({
            "recipe_id": recipe_id,
            "name": name,  # ← From Pickle DataFrame
            "category": category,  # ← From Pickle DataFrame
            "images": images,  # ← From Pickle DataFrame
            "ingredient_parts": ingredient_parts,  # ← From Pickle DataFrame
            "instructions": instructions,  # ← From Pickle DataFrame
            "aggregated_rating": aggregated_rating,  # ← From Pickle DataFrame (Real rating!)
            "review_count": review_count,  # ← From Pickle DataFrame (Real reviews!)
            "total_time": total_time,  # ← From Pickle DataFrame
            "description": description,  # ← From Pickle DataFrame
            "keywords": [],
            "es_score": es_score,
            "tfidf_score": tfidf_score,
            "highlight": highlight,
        })

    # normalize score ก่อนผสม
    es_scores = [x["es_score"] for x in temp_results]
    tfidf_scores = [x["tfidf_score"] for x in temp_results]

    es_norm = minmax_normalize(es_scores)
    tfidf_norm = minmax_normalize(tfidf_scores)

    for i, item in enumerate(temp_results):
        item["score"] = alpha * es_norm[i] + (1 - alpha) * tfidf_norm[i]

    # sort ตาม hybrid score
    temp_results.sort(key=lambda x: x["score"], reverse=True)

    return temp_results[:top_k]

#TEST
if __name__ == "__main__":
    results = search("spicy chicken", top_k=5, candidate_k=100, alpha=0.5)

    for r in results:
        print("-" * 60)
        print("Rank        :", results.index(r) + 1)
        print("recipe_id   :", r["recipe_id"])
        print("name        :", r["name"])
        print("category    :", r["category"])
        print("time        :", r["total_time"])
        print("es_score    :", round(r["es_score"], 4))
        print("tfidf_score :", round(r["tfidf_score"], 4))
        print("final_score :", round(r["score"], 4))
        if r.get("highlight"):
            print("highlight   :", r["highlight"][:100] + "...")