"""
ML Comparison API - Demonstrate ML vs Baseline performance
Shows evidence that TF-IDF enhances recommendation quality
"""
from flask import Blueprint, request, jsonify
from .api_auth import require_auth
from services.shared_indexer import get_shared_indexer
import logging

logger = logging.getLogger(__name__)

api_ml_comparison_bp = Blueprint('api_ml_comparison', __name__)

@api_ml_comparison_bp.route('/api/recommendations/compare', methods=['GET'])
@require_auth
def compare_ml_vs_baseline():
    """
    Compare ML recommendations vs Baseline (popular recipes)

    Returns side-by-side comparison to demonstrate ML enhancement:
    - Personalization: ML uses user's taste, baseline doesn't
    - Relevance: ML shows similar recipes, baseline shows generic popular
    - Diversity: ML explores user's preferences, baseline shows same for everyone
    """
    from models.models import db, User, Bookmark
    import pandas as pd

    user_id = request.user.user_id
    top_k = request.args.get('top_k', 10, type=int)

    logger.info(f"[ML-COMPARE] Comparing ML vs Baseline for user {user_id}")

    try:
        # Get user's bookmarks
        user_bookmarks = Bookmark.query.filter_by(user_id=user_id).all()

        if len(user_bookmarks) < 3:
            return jsonify({
                'error': 'Need at least 3 bookmarks to compare',
                'message': 'Bookmark more recipes to see personalized ML recommendations'
            }), 400

        # 1) Get ML Recommendations (TF-IDF)
        from .api_recommendations import get_ml_recommendations_internal
        ml_results = get_ml_recommendations_internal(user_id, top_k, folder_id=None)

        # 2) Get Baseline (Popular Recipes)
        from .api_recommendations import get_popular_recipes
        baseline_results = get_popular_recipes(top_k)

        # 3) Calculate Comparison Metrics
        indexer = get_shared_indexer()
        df = indexer.documents

        bookmarked_ids = [b.recipe_id for b in user_bookmarks]

        # Personalization Score: How many ML results match user's taste?
        ml_personalization = calculate_personalization_score(ml_results, bookmarked_ids, df)
        baseline_personalization = calculate_personalization_score(baseline_results, bookmarked_ids, df)

        # Diversity Score: How diverse are the recommendations?
        ml_diversity = calculate_diversity_score(ml_results)
        baseline_diversity = calculate_diversity_score(baseline_results)

        return jsonify({
            'comparison': {
                'ml_approach': {
                    'method': 'TF-IDF Content-Based Filtering',
                    'description': 'Personalized based on your bookmarked recipes',
                    'personalization_score': ml_personalization,
                    'diversity_score': ml_diversity,
                    'recommendations': ml_results[:5]  # Show top 5
                },
                'baseline_approach': {
                    'method': 'Popularity-Based (Most Rated)',
                    'description': 'Generic popular recipes (same for everyone)',
                    'personalization_score': baseline_personalization,
                    'diversity_score': baseline_diversity,
                    'recommendations': baseline_results[:5]  # Show top 5
                }
            },
            'ml_enhancement': {
                'personalization_improvement': f"{((ml_personalization - baseline_personalization) / max(baseline_personalization, 0.01) * 100):.1f}%",
                'diversity_improvement': f"{((ml_diversity - baseline_diversity) / max(baseline_diversity, 0.01) * 100):.1f}%",
                'conclusion': 'ML provides personalized recommendations based on your taste, while baseline shows generic popular items'
            }
        }), 200

    except Exception as e:
        logger.error(f"[ML-COMPARE] Error: {e}")
        return jsonify({'error': str(e)}), 500


def calculate_personalization_score(recommendations, bookmarked_ids, df):
    """
    Calculate how personalized recommendations are

    Score based on:
    - Category overlap with user's bookmarks
    - Ingredient overlap with user's preferences
    - Higher = More personalized
    """
    if not recommendations:
        return 0.0

    try:
        # Get user's preferred categories and ingredients
        user_categories = set()
        user_ingredients = set()

        for recipe_id in bookmarked_ids[:10]:  # Sample first 10
            if recipe_id in df.index:
                recipe = df.loc[recipe_id]
                if pd.notna(recipe.get('category')):
                    user_categories.add(recipe['category'])
                if pd.notna(recipe.get('ingredient_parts')):
                    ingredients = str(recipe['ingredient_parts']).lower().split()
                    user_ingredients.update(ingredients[:20])  # Top 20 ingredients

        # Calculate overlap
        score = 0.0
        for rec in recommendations[:10]:
            rec_id = rec['recipe_id']
            if rec_id in df.index:
                recipe = df.loc[rec_id]

                # Category match
                if pd.notna(recipe.get('category')) and recipe['category'] in user_categories:
                    score += 0.3

                # Ingredient overlap
                if pd.notna(recipe.get('ingredient_parts')):
                    rec_ingredients = set(str(recipe['ingredient_parts']).lower().split())
                    overlap = len(rec_ingredients & user_ingredients)
                    if overlap > 0:
                        score += min(overlap * 0.01, 0.7)  # Max 0.7 for ingredients

        return min(score / len(recommendations), 1.0)

    except Exception as e:
        logger.error(f"Error calculating personalization: {e}")
        return 0.0


def calculate_diversity_score(recommendations):
    """
    Calculate category diversity in recommendations

    Higher score = More diverse categories
    """
    if not recommendations:
        return 0.0

    try:
        categories = set()
        for rec in recommendations[:10]:
            if rec.get('category'):
                categories.add(rec['category'])

        # Diversity = unique categories / total recommendations
        return len(categories) / min(len(recommendations), 10)

    except Exception as e:
        logger.error(f"Error calculating diversity: {e}")
        return 0.0
