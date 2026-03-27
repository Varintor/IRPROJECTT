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
            }
        },
    )
    print(f"Created index: {INDEX_NAME}")

def generate_actions(df):
    for i, row in df.iterrows():
        yield {
            "_index": INDEX_NAME,
            "_id": int(i),
            "_source": {
                "recipe_id": int(row["recipe_id"]),
                "name": str(row["name"]),
                "category": str(row["category"]),
                "processed_text": str(row["processed_text"]),
                "images": str(row["images"]) if "images" in df.columns else "",
                "ingredient_parts": str(row["ingredient_parts"]) if "ingredient_parts" in df.columns else "",
                "instructions": str(row["instructions"]) if "instructions" in df.columns else "",

            },
        }

def push_to_es():
    indexer = Indexer_manual()
    df = indexer.documents.copy()

    success, errors = helpers.bulk(es, generate_actions(df))
    print(f"Indexed {success} documents")

    if errors:
        print("Some documents failed to index")
        print(errors[:3])

def verify_index():
    count = es.count(index=INDEX_NAME)["count"]
    print(f"Documents in index '{INDEX_NAME}': {count}")

if __name__ == "__main__":
    print("Elasticsearch connected:", es.ping())
    create_index()
    push_to_es()
    verify_index()
    print("DONE")