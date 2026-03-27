from flask import Flask, request, jsonify
from elastic_search import search as elastic_search

app = Flask(__name__)

@app.route("/")
def home():
    return "IR search API (Elasticsearch)"

@app.route("/search")
def search_api():
    q = request.args.get("q", "").strip()

    if not q:
        return jsonify([])

    try:
        results = elastic_search(q, top_k=5)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("starting flask")
    app.run(debug=True)