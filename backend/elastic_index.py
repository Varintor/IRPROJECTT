from pathlib import Path
from elasticsearch import Elasticsearch, helpers
from indexer_manual import Indexer_manual

INDEX_NAME = "recipes"

ca_cert_path = r"C:\Users\taitl\OneDrive - Chiang Mai University\เดสก์ท็อป\IRPROJECT\http_ca.crt"

es = Elasticsearch(
    "http://localhost:9200",
    basic_auth=("elastic", "71WOZgaJD_=*y7kku*qe"),
)

def create_index():
    if es.indices.exists(index=INDEX_NAME):
        es.indices.delete(index=INDEX_NAME)
        print(f"Deleted old index: {INDEX_NAME}")

    es.indices.create(
        index=INDEX_NAME,
        mappings={
            "properties": {
                "recipe_id": {"type": "integer"},
                "name": {"type": "text"},
                "category": {"type": "text"},
                "processed_text": {"type": "text"},
                "images": {"type": "keyword"},
                "ingredient_parts": {"type": "text"},
                "instructions": {"type": "text"},
                "aggregated_rating": {"type": "float"},
                "review_count": {"type": "integer"},
            }
        },
    )
    print(f"Created index: {INDEX_NAME}")

def generate_actions(df):
    for i, row in df.iterrows():
        source = {
            "_index": INDEX_NAME,
            "_id": int(row["recipe_id"]),
            "_source": {
                "recipe_id": int(row["recipe_id"]),
                "name": str(row["name"]),
                "category": str(row["category"]),
                "processed_text": str(row["processed_text"]),
                "images": str(row.get("images", "")),
                "ingredient_parts": str(row.get("ingredient_parts", "")),
                "instructions": str(row.get("instructions", "")),
            }
        }

        # Add rating if available
        if 'aggregated_rating' in df.columns:
            source["_source"]["aggregated_rating"] = float(row.get("aggregated_rating", 0))
        if 'review_count' in df.columns:
            source["_source"]["review_count"] = int(row.get("review_count", 0))

        yield source

def push_to_es():
    indexer = IndexerFromPKL()
    df = indexer.documents.copy()

    print(f"Indexing {len(df)} documents to Elasticsearch...")

    success, errors = helpers.bulk(es, generate_actions(df))
    print(f"✅ Indexed {success} documents")

    if errors:
        print(f"⚠️  Failed to index {errors} documents")

    return success, errors

def verify_index():
    count = es.count(index=INDEX_NAME)["count"]
    print(f"Documents in index '{INDEX_NAME}': {count}")

if __name__ == "__main__":
    print("Elasticsearch connected:", es.ping())
    create_index()
    push_to_es()
    verify_index()
    print("DONE")