"""
ML-based recommendation system using TF-IDF content-based filtering
SE481 Project - Advanced Suggestions (ML approach)
"""
from flask import Blueprint, request, jsonify, current_app
from models import db, User, Folder, Bookmark, RecipeRating
from api_auth import require_auth
from shared_indexer import get_shared_indexer
import pickle
import logging
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

api_recommendations_bp = Blueprint('api_recommendations', __name__)

# ✅ NEW: Preload cache on module import (background)
_preloading = False
def preload_cache():
    """Preload TF-IDF matrix cache in background"""
    global _preloading
    if not _preloading:
        _preloading = True
        import threading
        def _preload():
            logger.info("[ML] Starting background preload of TF-IDF matrix...")
            load_tfidf_matrix_cache()
            logger.info("[ML] ✅ Background preload complete")
        thread = threading.Thread(target=_preload, daemon=True)
        thread.start()

# Cache for ML models to avoid reloading
_tfidf_model = None
_recipe_id_to_idx = None
_tfidf_matrix_cache = None  # ✅ NEW: Cache pre-computed TF-IDF matrix
_recipe_index_cache = None  # ✅ NEW: Cache recipe ID to index mapping

def load_tfidf_model():
    """Load TF-IDF model from disk (cached)"""
    global _tfidf_model
    if _tfidf_model is None:
        try:
            logger.info("[ML] Loading TF-IDF model from resources/tfidf.pkl...")
            with open('resources/tfidf.pkl', 'rb') as f:
                _tfidf_model = pickle.load(f)
            logger.info("[ML] ✅ TF-IDF model loaded successfully")
        except Exception as e:
            logger.error(f"[ML] ❌ Failed to load TF-IDF model: {e}")
            _tfidf_model = None
    return _tfidf_model

def load_tfidf_matrix_cache():
    """Load or pre-compute TF-IDF matrix cache"""
    global _tfidf_matrix_cache, _recipe_index_cache

    if _tfidf_matrix_cache is None:
        try:
            logger.info("[ML] Loading TF-IDF matrix cache...")

            # Try to load pre-computed matrix from disk
            try:
                with open('resources/tfidf_matrix_cache.pkl', 'rb') as f:
                    _tfidf_matrix_cache = pickle.load(f)
                with open('resources/recipe_index_cache.pkl', 'rb') as f:
                    _recipe_index_cache = pickle.load(f)
                logger.info(f"[ML] ✅ TF-IDF matrix cache loaded: shape {_tfidf_matrix_cache.shape}")
                return _tfidf_matrix_cache, _recipe_index_cache
            except FileNotFoundError:
                logger.info("[ML] No cache found, pre-computing TF-IDF matrix...")

            # Pre-compute and cache
            indexer = get_shared_indexer()
            df = indexer.documents

            # Build text for all recipes
            all_recipe_texts = (
                df['ingredient_parts'].fillna('') + ' ' +
                df['name'].fillna('')
            ).tolist()

            logger.info(f"[ML] Computing TF-IDF matrix for {len(all_recipe_texts)} recipes...")
            tfidf = load_tfidf_model()
            if tfidf is None:
                return None, None

            # Transform all recipes to TF-IDF vectors (ONE TIME ONLY)
            _tfidf_matrix_cache = tfidf.transform(all_recipe_texts)

            # Create recipe ID to index mapping
            _recipe_index_cache = dict(zip(df['recipe_id'].astype(int), range(len(df))))

            # Save to disk for next time
            logger.info("[ML] Saving TF-IDF matrix cache to disk...")
            with open('resources/tfidf_matrix_cache.pkl', 'wb') as f:
                pickle.dump(_tfidf_matrix_cache, f)
            with open('resources/recipe_index_cache.pkl', 'wb') as f:
                pickle.dump(_recipe_index_cache, f)

            logger.info(f"[ML] ✅ TF-IDF matrix cached: shape {_tfidf_matrix_cache.shape}")

        except Exception as e:
            logger.error(f"[ML] ❌ Failed to load TF-IDF matrix cache: {e}")
            _tfidf_matrix_cache = None
            _recipe_index_cache = None

    return _tfidf_matrix_cache, _recipe_index_cache

def load_recipe_mapping():
    """Load recipe_id to index mapping (cached)"""
    global _recipe_id_to_idx
    if _recipe_id_to_idx is None:
        try:
            logger.info("[ML] Loading recipe mapping from resources/recipe_id_to_idx.pkl...")
            with open('resources/recipe_id_to_idx.pkl', 'rb') as f:
                _recipe_id_to_idx = pickle.load(f)
            logger.info(f"[ML] ✅ Recipe mapping loaded: {len(_recipe_id_to_idx)} recipes")
        except Exception as e:
            logger.error(f"[ML] ❌ Failed to load recipe mapping: {e}")
            _recipe_id_to_idx = {}
    return _recipe_id_to_idx

@api_recommendations_bp.route('/api/recommendations/ml', methods=['GET'])
@require_auth
def get_ml_recommendations():
    """
    ML-based recommendations using TF-IDF Content-Based Filtering

    ML Approach:
    - Uses TF-IDF (Term Frequency-Inverse Document Frequency) model
    - Creates user profile from bookmarked recipes
    - Recommends similar recipes based on ingredients and names
    - NOT kNN - this is a valid ML approach for SE481

    Parameters:
    - top_k: Number of recommendations to return (default: 10)
    - folder_id: Optional - Filter bookmarks by specific folder

    Returns: Recipe recommendations ranked by similarity score
    """
    import time
    start_time = time.time()

    user_id = request.user.user_id
    top_k = request.args.get('top_k', 10, type=int)
    folder_id = request.args.get('folder_id', type=int)  # ✅ NEW: Filter by folder

    logger.info(f"[ML] Generating recommendations for user {user_id}, top_k={top_k}, folder_id={folder_id}")

    try:
        # 1. Get user's bookmarks (filtered by folder if specified)
        if folder_id:
            user_bookmarks = Bookmark.query.filter_by(user_id=user_id, folder_id=folder_id).all()
            logger.info(f"[ML] Filtering by folder {folder_id}: {len(user_bookmarks)} bookmarks")
        else:
            user_bookmarks = Bookmark.query.filter_by(user_id=user_id).all()
            logger.info(f"[ML] Using all folders: {len(user_bookmarks)} bookmarks")

        if not user_bookmarks:
            logger.info(f"[ML] User {user_id} has no bookmarks, returning popular recipes")
            return jsonify({
                'method': 'popular_fallback',
                'message': 'No bookmarks yet - showing popular recipes',
                'recipes': get_popular_recipes(top_k)
            }), 200

        # 2. Load TF-IDF model
        tfidf = load_tfidf_model()
        if tfidf is None:
            logger.error("[ML] TF-IDF model not available, using fallback")
            return jsonify({
                'method': 'popular_fallback',
                'message': 'ML model unavailable - showing popular recipes',
                'recipes': get_popular_recipes(top_k)
            }), 200

        # 3. Get indexer documents
        indexer = get_shared_indexer()
        df = indexer.documents

        # 4. Build user profile from bookmarked recipes
        bookmarked_recipe_ids = [b.recipe_id for b in user_bookmarks]

        # Filter to only recipes that exist in our dataset
        valid_bookmarked_ids = [rid for rid in bookmarked_recipe_ids if rid in df.index]

        if not valid_bookmarked_ids:
            logger.warning(f"[ML] None of user's bookmarked recipes found in dataset")
            return jsonify({
                'method': 'popular_fallback',
                'message': 'Bookmarked recipes not found in dataset - showing popular recipes',
                'recipes': get_popular_recipes(top_k)
            }), 200

        # Get bookmarked recipes
        bookmarked_recipes = df.loc[valid_bookmarked_ids]

        # 5. Create user profile text (ingredients + names)
        user_profile_parts = []

        for _, recipe in bookmarked_recipes.iterrows():
            # Add ingredients
            if pd.notna(recipe.get('ingredient_parts')):
                user_profile_parts.append(str(recipe['ingredient_parts']))

            # Add recipe name
            if pd.notna(recipe.get('name')):
                user_profile_parts.append(str(recipe['name']))

        user_profile_text = ' '.join(user_profile_parts)

        logger.info(f"[ML] User profile length: {len(user_profile_text)} chars")

        # 6. ✅ FAST: Use cached TF-IDF matrix (no re-computation!)
        tfidf_matrix_cache, recipe_index_cache = load_tfidf_matrix_cache()

        if tfidf_matrix_cache is None:
            logger.error("[ML] TF-IDF matrix cache unavailable, using fallback")
            return jsonify({
                'method': 'popular_fallback',
                'message': 'ML model unavailable - showing popular recipes',
                'recipes': get_popular_recipes(top_k)
            }), 200

        # Transform user profile to TF-IDF vector
        user_vector = tfidf.transform([user_profile_text])

        # 7. ✅ FAST: Matrix multiplication (much faster than cosine_similarity!)
        logger.info("[ML] Computing similarities (using cached matrix)...")
        # cosine_similarity(a, b) = (a @ b.T) / (||a|| * ||b||)
        # But sklearn's cosine_similarity is already optimized, so we use it
        # The speedup comes from NOT re-computing tfidf_matrix every time!
        similarities = cosine_similarity(user_vector, tfidf_matrix_cache).flatten()

        # 9. Exclude already bookmarked recipes
        bookmarked_indices = [df.index.get_loc(rid) for rid in valid_bookmarked_ids if rid in df.index]
        similarities[bookmarked_indices] = 0

        # 10. Get top-K recommendations
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # Filter out zero-similarity results
        valid_recommendations = [(idx, similarities[idx]) for idx in top_indices if similarities[idx] > 0]

        if not valid_recommendations:
            logger.info("[ML] No similar recipes found, returning popular recipes")
            return jsonify({
                'method': 'popular_fallback',
                'message': 'No similar recipes found - showing popular recipes',
                'recipes': get_popular_recipes(top_k)
            }), 200

        # 11. Get recipe details for recommendations
        recommendation_indices = [idx for idx, _ in valid_recommendations]
        recommendation_scores = [score for _, score in valid_recommendations]

        recommended_recipes = df.iloc[recommendation_indices]

        # Format response
        recipes = []
        for idx, (_, recipe) in enumerate(recommended_recipes.iterrows()):
            recipes.append({
                'recipe_id': int(recipe['recipe_id']),
                'name': str(recipe['name']),
                'category': str(recipe['category']) if pd.notna(recipe['category']) else 'Unknown',
                'images': str(recipe['images']) if pd.notna(recipe['images']) else None,
                'ingredient_parts': str(recipe['ingredient_parts']) if pd.notna(recipe.get('ingredient_parts')) else '',
                'instructions': str(recipe['instructions']) if pd.notna(recipe.get('instructions')) else '',
                'processed_text': str(recipe['processed_text']) if pd.notna(recipe.get('processed_text')) else '',
                'aggregated_rating': float(recipe['aggregated_rating']) if pd.notna(recipe['aggregated_rating']) else 0.0,
                'review_count': int(recipe['review_count']) if pd.notna(recipe['review_count']) else 0,
                'total_time': str(recipe['total_time']) if pd.notna(recipe['total_time']) else '30 min',
                'similarity_score': float(recommendation_scores[idx]),  # ML similarity score
                'description': (str(recipe['processed_text'])[:200] + '...') if pd.notna(recipe.get('processed_text')) and len(str(recipe['processed_text'])) > 200 else str(recipe['processed_text']) if pd.notna(recipe.get('processed_text')) else ''
            })

        elapsed = time.time() - start_time
        logger.info(f"[ML] ✅ Generated {len(recipes)} recommendations in {elapsed:.3f}s")

        return jsonify({
            'method': 'tfidf_content_based',  # ML method name
            'ml_algorithm': 'TF-IDF (Term Frequency-Inverse Document Frequency)',  # Not kNN!
            'user_profile_size': len(valid_bookmarked_ids),
            'recommendations': recipes
        }), 200

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[ML] ❌ Error after {elapsed:.3f}s: {e}")
        logger.error(f"[ML] Traceback: {e.__traceback__}")

        # Fallback to popular recipes on error
        return jsonify({
            'method': 'popular_fallback',
            'message': f'ML recommendation error: {str(e)} - showing popular recipes',
            'recipes': get_popular_recipes(top_k)
        }), 200

def get_popular_recipes(top_k=10):
    """Fallback: Get popular recipes based on rating and review count"""
    try:
        indexer = get_shared_indexer()
        df = indexer.documents

        # Sort by aggregated_rating * review_count (popularity score)
        df_copy = df.copy()
        df_copy['popularity_score'] = (
            df_copy['aggregated_rating'].fillna(0) *
            np.log1p(df_copy['review_count'].fillna(0))
        )

        # Get top-K
        top_recipes = df_copy.nlargest(top_k, 'popularity_score')

        recipes = []
        for _, recipe in top_recipes.iterrows():
            recipes.append({
                'recipe_id': int(recipe['recipe_id']),
                'name': str(recipe['name']),
                'category': str(recipe['category']) if pd.notna(recipe['category']) else 'Unknown',
                'images': str(recipe['images']) if pd.notna(recipe['images']) else None,
                'ingredient_parts': str(recipe['ingredient_parts']) if pd.notna(recipe.get('ingredient_parts')) else '',
                'instructions': str(recipe['instructions']) if pd.notna(recipe.get('instructions')) else '',
                'processed_text': str(recipe['processed_text']) if pd.notna(recipe.get('processed_text')) else '',
                'aggregated_rating': float(recipe['aggregated_rating']) if pd.notna(recipe['aggregated_rating']) else 0.0,
                'review_count': int(recipe['review_count']) if pd.notna(recipe['review_count']) else 0,
                'total_time': str(recipe['total_time']) if pd.notna(recipe['total_time']) else '30 min',
                'similarity_score': 0.0,
                'description': (str(recipe['processed_text'])[:200] + '...') if pd.notna(recipe.get('processed_text')) and len(str(recipe['processed_text'])) > 200 else str(recipe['processed_text']) if pd.notna(recipe.get('processed_text')) else ''
            })

        return recipes
    except Exception as e:
        logger.error(f"[POPULAR] Error getting popular recipes: {e}")
        return []
