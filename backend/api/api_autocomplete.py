"""
Auto-Completion API for Search Query Suggestions
Provides real-time suggestions as user types (like Google search)
"""
from flask import Blueprint, request, jsonify
from services.shared_indexer import get_shared_indexer
import logging

logger = logging.getLogger(__name__)

api_autocomplete_bp = Blueprint('api_autocomplete', __name__)

@api_autocomplete_bp.route('/api/search/suggestions', methods=['GET'])
def get_search_suggestions():
    """
    Get search query suggestions based on partial input

    Exciting Feature: Real-time autocomplete like Google!
    - Suggests recipe names as user types
    - Shows popular searches
    - Learns from search history (if available)

    Args:
        q: Partial query string
        limit: Number of suggestions (default: 5)
    """
    query = request.args.get('q', '').strip().lower()
    limit = request.args.get('limit', 5, type=int)

    if not query or len(query) < 2:
        return jsonify({'suggestions': []})

    logger.info(f"[AUTOCOMPLETE] Getting suggestions for: '{query}'")

    try:
        indexer = get_shared_indexer()
        df = indexer.documents

        # Strategy 1: Match recipe names starting with query
        name_matches = df[
            df['name'].str.lower().str.startswith(query, na=False)
        ].head(limit * 2)

        # Strategy 2: Match ingredients starting with query
        ingredient_matches = df[
            df['ingredient_parts'].str.lower().str.contains(query, na=False)
        ].head(limit)

        # Strategy 3: Popular searches (most searched terms)
        # For now, use recipe frequency as proxy for popularity
        popular_matches = df[
            df['name'].str.lower().str.contains(query, na=False)
        ].head(limit)

        # Combine and deduplicate
        suggestions = []
        seen = set()

        # Add name matches (highest priority)
        for _, recipe in name_matches.iterrows():
            if recipe['name'] not in seen:
                suggestions.append({
                    'text': recipe['name'],
                    'type': 'recipe_name',
                    'category': recipe.get('category', 'Recipe'),
                    'image': recipe.get('images', '')
                })
                seen.add(recipe['name'])

        # Add ingredient matches
        for _, recipe in ingredient_matches.iterrows():
            if recipe['name'] not in seen and len(suggestions) < limit:
                suggestions.append({
                    'text': recipe['name'],
                    'type': 'ingredient_match',
                    'category': recipe.get('category', 'Recipe'),
                    'image': recipe.get('images', '')
                })
                seen.add(recipe['name'])

        # Add popular matches
        for _, recipe in popular_matches.iterrows():
            if recipe['name'] not in seen and len(suggestions) < limit:
                suggestions.append({
                    'text': recipe['name'],
                    'type': 'popular',
                    'category': recipe.get('category', 'Recipe'),
                    'image': recipe.get('images', '')
                })
                seen.add(recipe['name'])

        logger.info(f"[AUTOCOMPLETE] ✅ Found {len(suggestions)} suggestions")

        return jsonify({
            'query': query,
            'suggestions': suggestions[:limit]
        })

    except Exception as e:
        logger.error(f"[AUTOCOMPLETE] ❌ Error: {e}")
        return jsonify({'suggestions': []})


@api_autocomplete_bp.route('/api/search/trending', methods=['GET'])
def get_trending_searches():
    """
    Get trending/popular search terms

    Useful Feature: Shows what others are searching for
    - Popular recipe categories
    - Trending ingredients
    - Most searched terms
    """
    try:
        indexer = get_shared_indexer()
        df = indexer.documents

        # Get top categories by recipe count
        top_categories = df['category'].value_counts().head(10)

        # Get popular ingredients (simplified)
        # In production, this would use search history analytics
        trending = []

        for category, count in top_categories.items():
            trending.append({
                'term': category,
                'type': 'category',
                'count': int(count)
            })

        return jsonify({
            'trending': trending
        })

    except Exception as e:
        logger.error(f"[TRENDING] Error: {e}")
        return jsonify({'trending': []})
