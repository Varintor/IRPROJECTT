from pathlib import Path

import numpy as np
from elasticsearch import Elasticsearch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from data_loader import get_documents

INDEX_NAME = "recipes"

es = Elasticsearch(
    "http://localhost:9200",
    basic_auth=("elastic", "71WOZgaJD_=*y7kku*qe"),
)


# LOAD CUSTOM TF-IDF INDEX (lazy load)
documents = get_documents()

# ใช้ unigram ตามที่ต้องการ
tfidf_vectorizer = TfidfVectorizer(ngram_range=(1, 1))
X_tfidf = tfidf_vectorizer.fit_transform(documents["processed_text"])


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
    body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["name^2", "category", "processed_text"],
                "fuzziness": "AUTO"
            }
        }
    }

    res = es.search(
        index=INDEX_NAME,
        body=body,
        size=top_k,
    )

    return res["hits"]["hits"]


def tfidf_search_scores(query):
    """
    คำนวณ custom TF-IDF cosine similarity กับทุก document
    แล้วคืนเป็น dict: recipe_id -> score
    """
    q_vec = tfidf_vectorizer.transform([query])
    sims = cosine_similarity(q_vec, X_tfidf).flatten()

    score_map = dict(zip(documents["recipe_id"].astype(int), sims))
    return score_map


# HYBRID SEARCH
def search(query, top_k=5, candidate_k=100, alpha=0.5):
    """
    alpha = น้ำหนักของ Elasticsearch score
    (1 - alpha) = น้ำหนักของ custom TF-IDF score
    """

    # 1) ดึง candidate จาก Elasticsearch ก่อน
    es_hits = elastic_retrieve(query, top_k=candidate_k)

    # 2) คำนวณ TF-IDF score custom
    tfidf_score_map = tfidf_search_scores(query)

    temp_results = []

    for hit in es_hits:
        src = hit["_source"]
        recipe_id = int(src["recipe_id"])
        es_score = float(hit["_score"])
        tfidf_score = float(tfidf_score_map.get(recipe_id, 0.0))

        temp_results.append({
            "recipe_id": recipe_id,
            "name": src.get("name", ""),
            "category": src.get("category", ""),
            "images": src.get("images", ""),
            "ingredient_parts": src.get("ingredient_parts", ""),
            "instructions": src.get("instructions", ""),
            "aggregated_rating": src.get("aggregated_rating", 0),
            "review_count": src.get("review_count", 0),
            "es_score": es_score,
            "tfidf_score": tfidf_score,
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
        print("-" * 50)
        print("recipe_id   :", r["recipe_id"])
        print("name        :", r["name"])
        print("category    :", r["category"])
        print("es_score    :", round(r["es_score"], 4))
        print("tfidf_score :", round(r["tfidf_score"], 4))
        print("final_score :", round(r["score"], 4))