import sys
import os

# Add current directory to Python path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from utils.config import Config
from models.models import db
from services.elastic_search import search as elastic_search
from services.spell_checker import init_spell_checker
from services.shared_indexer import preload_indexer, get_shared_indexer
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS for ALL origins in development
CORS(app, origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174", "http://localhost:5175", "http://localhost:8080"], supports_credentials=True)

# Initialize database
db.init_app(app)

# ✅ FIX: Ensure database sessions are cleaned up after each request
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up database session after each request"""
    db.session.remove()
    logger.debug("Database session cleaned up")

# Import and register blueprints AFTER app is created (avoid circular import)
from api.api_auth import api_auth_bp
from api.api_bookmarks import api_bookmarks_bp
from api.api_recommendations import api_recommendations_bp
from api.api_ml_comparison import api_ml_comparison_bp
from api.api_autocomplete import api_autocomplete_bp
from api.api_faceted_search import api_faceted_search_bp  # ✅ NEW: Faceted search API

app.register_blueprint(api_auth_bp)
app.register_blueprint(api_bookmarks_bp)
app.register_blueprint(api_recommendations_bp)
app.register_blueprint(api_ml_comparison_bp)
app.register_blueprint(api_autocomplete_bp)
app.register_blueprint(api_faceted_search_bp)  # ✅ NEW: Register faceted search

# ✅ NEW: Preload ML models in background
from api.api_recommendations import preload_cache
preload_cache()

# Spell checker (using shared indexer)
spell_checker = None
_spell_checker_loaded = False

def initialize_spell_checker():
    """Initialize spell checker on first use (uses shared indexer)"""
    global spell_checker, _spell_checker_loaded
    if not _spell_checker_loaded:
        logger.info("📝 Initializing spell checker (using shared indexer)...")
        indexer = get_shared_indexer()
        documents = indexer.documents
        spell_checker = init_spell_checker(documents)
        _spell_checker_loaded = True
        logger.info("✅ Spell checker initialized")
    return spell_checker

@app.before_request
def load_spell_checker_if_needed():
    """Load spell checker on first search request (NOT for health check)"""
    # Only load for search endpoints, not health check or auth
    if request.path.startswith('/search') or request.path.startswith('/api/spellcheck'):
        initialize_spell_checker()

# Health check endpoint
@app.route("/api/health", methods=["GET"])
def health_check():
    """Test API connection"""
    logger.info("✅ Health check called")
    return jsonify({
        "status": "ok",
        "message": "Backend is running!",
        "database": "PostgreSQL connected",
        "search": "Elasticsearch ready"
    })

# Test database endpoint
@app.route("/api/test-db", methods=["GET"])
def test_database():
    """Test database connection"""
    import time
    start = time.time()
    try:
        from models import User
        count = User.query.count()
        elapsed = time.time() - start
        logger.info(f"✅ Database test: {count} users in {elapsed:.3f}s")
        return jsonify({
            "status": "ok",
            "user_count": count,
            "query_time": f"{elapsed:.3f}s"
        })
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"❌ Database test failed after {elapsed:.3f}s: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "query_time": f"{elapsed:.3f}s"
        }), 500

# Test endpoint
@app.route("/api/test", methods=["GET", "POST"])
def test_endpoint():
    """Test CORS and API connection"""
    logger.info(f"✅ Test endpoint called - Method: {request.method}")
    return jsonify({
        "message": "CORS is working!",
        "received_method": request.method,
        "timestamp": str(datetime.now())
    })

# Spell check endpoint
@app.route("/api/spellcheck", methods=["POST"])
def spell_check_endpoint():
    """Check spelling and suggest corrections"""
    logger.info("✅ Spell check called")

    if not spell_checker:
        # Return no corrections instead of error
        return jsonify({
            "original_query": "",
            "corrected_query": "",
            "corrections": [],
            "has_corrections": False,
            "suggestions": []
        }), 200

    data = request.get_json()
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        # Get corrections
        corrected_query, corrections, suggestions = spell_checker.correct_query(query)

        response = {
            "original_query": query,
            "corrected_query": corrected_query,
            "corrections": corrections,
            "has_corrections": len(corrections) > 0,
            "suggestions": suggestions
        }

        logger.info(f"Spell check: '{query}' -> '{corrected_query}' ({len(corrections)} corrections)")

        return jsonify(response)

    except Exception as e:
        logger.error(f"Spell check error: {str(e)}")
        # Return no corrections instead of error
        return jsonify({
            "original_query": query,
            "corrected_query": query,
            "corrections": [],
            "has_corrections": False,
            "suggestions": []
        }), 200

# Main routes
@app.route("/")
def index():
    return render_template('index.html')

# ✅ Helper: Convert ISO 8601 duration to human-readable format
def format_duration(duration_str: str) -> str:
    """Convert PT2H42M format to '2h 42m' or similar"""
    if not duration_str or not duration_str.startswith('PT'):
        return "30 min"

    try:
        import re
        # Extract hours and minutes from PT2H42M format
        hours = re.search(r'(\d+)H', duration_str)
        minutes = re.search(r'(\d+)M', duration_str)

        h = int(hours.group(1)) if hours else 0
        m = int(minutes.group(1)) if minutes else 0

        if h > 0 and m > 0:
            return f"{h}h {m}m"
        elif h > 0:
            return f"{h}h"
        elif m > 0:
            return f"{m} min"
        else:
            return "30 min"
    except:
        return "30 min"

# ✅ NEW: Get recipes by IDs (for random display)
@app.route("/api/recipes/by-ids", methods=["POST"])
def get_recipes_by_ids():
    """Get multiple recipes by their IDs"""
    data = request.get_json()
    recipe_ids = data.get("recipe_ids", [])

    if not recipe_ids:
        return jsonify({"error": "No recipe_ids provided"}), 400

    try:
        indexer = get_shared_indexer()
        df = indexer.documents

        # Query recipes by IDs
        recipes = []
        for rid in recipe_ids:
            try:
                # Fast lookup using indexed DataFrame
                if hasattr(df, '_indexed_by_id'):
                    # O(1) lookup if indexed
                    doc_row = df.loc[rid]
                else:
                    # Fallback to O(N) scan
                    doc_rows = df[df['recipe_id'] == rid]
                    if len(doc_rows) == 0:
                        continue
                    doc_row = doc_rows.iloc[0]

                recipes.append({
                    "recipe_id": int(doc_row['recipe_id']),
                    "name": str(doc_row.get('name', '')),
                    "category": str(doc_row.get('category', 'General')),
                    "images": str(doc_row.get('images', '')),
                    "ingredient_parts": str(doc_row.get('ingredient_parts', '')),
                    "instructions": str(doc_row.get('instructions', '')),
                    "total_time": format_duration(str(doc_row.get('total_time', ''))),
                    "aggregated_rating": float(doc_row.get('aggregated_rating', 0.0)),
                    "review_count": int(doc_row.get('review_count', 0))
                })
            except Exception as e:
                logger.warning(f"Recipe ID {rid} not found: {e}")
                continue

        logger.info(f"✅ Retrieved {len(recipes)}/{len(recipe_ids)} recipes by IDs")
        return jsonify({"recipes": recipes})

    except Exception as e:
        logger.error(f"❌ Error getting recipes by IDs: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/search")
def search_api():
    q = request.args.get("q", "").strip()
    top_k = request.args.get("top_k", 5, type=int)

    logger.info(f"🔍 Search called - Query: '{q}', TopK: {top_k}")

    if not q:
        logger.warning("❌ Empty query received")
        return jsonify([])

    try:
        # Auto-correct query if spell checker is available
        if spell_checker:
            corrected_query, corrections, _ = spell_checker.correct_query(q)

            if corrections:
                logger.info(f"📝 Auto-corrected: '{q}' -> '{corrected_query}'")
                q = corrected_query  # Use corrected query

        results = elastic_search(q, top_k=top_k)
        logger.info(f"✅ Search successful - Found {len(results)} results")

        # Add spell correction info to response
        response_data = {
            "results": results,
            "query_used": q,
            "original_query": request.args.get("q", ""),
            "auto_corrected": len(corrections) > 0 if spell_checker else False
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"❌ Search error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Create database tables
with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully!")

if __name__ == "__main__":
    print("=" * 60)
    print("🔄 Preloading indexer at startup...")
    print("=" * 60)
    preload_indexer()  # PRELOAD before server starts!
    print("=" * 60)
    print("🚀 Starting Flask Backend Server...")
    print("=" * 60)
    print("📊 Database: PostgreSQL (recipe_app)")
    print("🔍 Search: Elasticsearch + TF-IDF")
    print("📦 Indexer: Preloaded (52K recipes)")
    print("🌐 API Server: http://localhost:5000")
    print("⚛️  Frontend: http://localhost:5173")
    print("=" * 60)
    print("✅ Available endpoints:")
    print("   - GET  /api/health  (Health check)")
    print("   - GET/POST /api/test   (CORS test)")
    print("   - GET  /search?q=xxx  (Search API)")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)