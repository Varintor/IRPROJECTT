"""
Faceted Search API - Advanced Filtering
Allows users to filter recipes by multiple dimensions (category, time, rating, ingredients)
"""
from flask import Blueprint, request, jsonify
from services.shared_indexer import get_shared_indexer
import pandas as pd
import logging

logger = logging.getLogger(__name__)

api_faceted_search_bp = Blueprint('api_faceted_search', __name__)

@api_faceted_search_bp.route('/api/search/faceted', methods=['POST'])
def faceted_search():
    """
    Advanced faceted search with multiple filters

    Exciting Feature: Filter like Amazon/Netflix!
    - Filter by category
    - Filter by cook time (quick, medium, long)
    - Filter by rating (4+ stars, 3+ stars)
    - Filter by ingredients (include/exclude)

    Args (JSON body):
        query: Search query (optional)
        filters: {
            category: str or [str]  (optional)
            min_time: int  (minutes, optional)
            max_time: int  (minutes, optional)
            min_rating: float  (optional)
            include_ingredients: [str]  (optional)
            exclude_ingredients: [str]  (optional)
        }
        sort: 'rating' | 'time' | 'reviews' (optional)
        limit: Number of results (default: 20)
    """
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        filters = data.get('filters', {})
        sort_by = data.get('sort', 'rating')
        limit = data.get('limit', 20)

        logger.info(f"[FACETED] Search - Query: '{query}', filters={filters}")
        logger.info(f"[FACETED] Sort by: {sort_by}, Limit: {limit}")

        # Get all recipes
        indexer = get_shared_indexer()
        df = indexer.documents.copy()

        # ✅ NEW: Apply query filter first (if query provided)
        if query and query.strip():
            query_lower = query.lower()
            # Search in name, ingredients, or instructions
            query_mask = (
                df['name'].str.lower().str.contains(query_lower, na=False) |
                df['ingredient_parts'].str.lower().str.contains(query_lower, na=False) |
                df['instructions'].str.lower().str.contains(query_lower, na=False)
            )
            df = df[query_mask]
            logger.info(f"[FACETED] Query filter applied: {len(df)} recipes match query '{query}'")

        # Apply filters
        filtered_df = apply_filters(df, filters)

        # Sort results
        filtered_df = sort_results(filtered_df, sort_by)

        # Limit results
        results = filtered_df.head(limit)

        # Format response
        recipes = []
        for _, recipe in results.iterrows():
            recipes.append({
                'recipe_id': int(recipe['recipe_id']),
                'name': str(recipe['name']),
                'category': str(recipe.get('category', 'Unknown')),
                'images': str(recipe.get('images', '')),
                'ingredient_parts': str(recipe.get('ingredient_parts', ''))[:200],
                'aggregated_rating': float(recipe.get('aggregated_rating', 0.0)),
                'review_count': int(recipe.get('review_count', 0)),
                'total_time': str(recipe.get('total_time', '30 min')),
                'description': str(recipe.get('processed_text', ''))[:150]
            })

        # Get filter metadata (for UI)
        facets = get_facet_metadata(df, filters)

        logger.info(f"[FACETED] ✅ Found {len(recipes)} results from {len(df)} total recipes")

        return jsonify({
            'results': recipes,
            'total': len(filtered_df),
            'filters_applied': filters,
            'facets': facets,  # Available filter options
            'sort_by': sort_by
        })

    except Exception as e:
        logger.error(f"[FACETED] ❌ Error: {e}")
        return jsonify({'error': str(e)}), 500


@api_faceted_search_bp.route('/api/search/facets', methods=['GET'])
def get_available_facets():
    """
    Get available facet options for filtering

    Useful Feature: Shows what filters are available
    - All categories with counts
    - Time ranges with counts
    - Rating ranges with counts
    """
    try:
        indexer = get_shared_indexer()
        df = indexer.documents

        facets = get_facet_metadata(df, {})

        return jsonify({
            'facets': facets
        })

    except Exception as e:
        logger.error(f"[FACETS] ❌ Error: {e}")
        return jsonify({'error': str(e)}), 500


def apply_filters(df, filters):
    """Apply all filters to dataframe"""
    filtered_df = df.copy()

    # Filter by category
    if filters.get('category'):
        category = filters['category']
        if isinstance(category, list):
            filtered_df = filtered_df[filtered_df['category'].isin(category)]
        else:
            filtered_df = filtered_df[filtered_df['category'] == category]

    # Filter by cook time (parse "PT2H30M" format or minutes)
    if filters.get('min_time') or filters.get('max_time'):
        filtered_df['time_minutes'] = filtered_df['total_time'].apply(parse_time_to_minutes)

        if filters.get('min_time'):
            filtered_df = filtered_df[filtered_df['time_minutes'] >= filters['min_time']]

        if filters.get('max_time'):
            filtered_df = filtered_df[filtered_df['time_minutes'] <= filters['max_time']]

    # Filter by rating
    if filters.get('min_rating'):
        filtered_df = filtered_df[
            filtered_df['aggregated_rating'] >= filters['min_rating']
        ]

    # Filter by ingredients (include)
    if filters.get('include_ingredients'):
        include_list = filters['include_ingredients']
        if isinstance(include_list, str):
            include_list = [include_list]

        mask = filtered_df['ingredient_parts'].str.lower().apply(
            lambda x: all(ing.lower() in str(x).lower() for ing in include_list)
        )
        filtered_df = filtered_df[mask]

    # Filter by ingredients (exclude)
    if filters.get('exclude_ingredients'):
        exclude_list = filters['exclude_ingredients']
        if isinstance(exclude_list, str):
            exclude_list = [exclude_list]

        mask = filtered_df['ingredient_parts'].str.lower().apply(
            lambda x: not any(ing.lower() in str(x).lower() for ing in exclude_list)
        )
        filtered_df = filtered_df[mask]

    return filtered_df


def sort_results(df, sort_by):
    """Sort results by specified criteria"""
    if sort_by == 'rating':
        return df.sort_values('aggregated_rating', ascending=False)
    elif sort_by == 'reviews':
        return df.sort_values('review_count', ascending=False)
    elif sort_by == 'time':
        # Sort by cook time (shortest first)
        df['_time_minutes'] = df['total_time'].apply(parse_time_to_minutes)
        return df.sort_values('_time_minutes', ascending=True)
    else:
        return df


def parse_time_to_minutes(time_str):
    """Parse ISO 8601 duration or minutes string to integer minutes"""
    if not time_str or pd.isna(time_str):
        return 30  # Default 30 min

    time_str = str(time_str)

    # Try ISO 8601 format (PT2H30M)
    if time_str.startswith('PT'):
        import re
        hours = re.search(r'(\d+)H', time_str)
        minutes = re.search(r'(\d+)M', time_str)

        h = int(hours.group(1)) if hours else 0
        m = int(minutes.group(1)) if minutes else 0
        return h * 60 + m

    # Try plain minutes
    try:
        return int(time_str)
    except:
        return 30


def get_facet_metadata(df, current_filters):
    """Get metadata for all available facets"""
    facets = {}

    # Categories with counts
    facets['categories'] = []
    category_counts = df['category'].value_counts().head(20)
    for cat, count in category_counts.items():
        facets['categories'].append({
            'name': str(cat),
            'count': int(count)
        })

    # Time ranges
    df['_time_minutes'] = df['total_time'].apply(parse_time_to_minutes)

    facets['time_ranges'] = [
        {
            'name': 'Quick (< 30 min)',
            'min': 0,
            'max': 30,
            'count': int(len(df[df['_time_minutes'] < 30]))
        },
        {
            'name': 'Medium (30-60 min)',
            'min': 30,
            'max': 60,
            'count': int(len(df[(df['_time_minutes'] >= 30) & (df['_time_minutes'] <= 60)]))
        },
        {
            'name': 'Long (> 60 min)',
            'min': 60,
            'max': 9999,
            'count': int(len(df[df['_time_minutes'] > 60]))
        }
    ]

    # Rating ranges
    facets['rating_ranges'] = [
        {
            'name': '5 Stars',
            'min': 5.0,
            'max': 5.0,
            'count': int(len(df[df['aggregated_rating'] >= 5.0]))
        },
        {
            'name': '4+ Stars',
            'min': 4.0,
            'max': 5.0,
            'count': int(len(df[df['aggregated_rating'] >= 4.0]))
        },
        {
            'name': '3+ Stars',
            'min': 3.0,
            'max': 5.0,
            'count': int(len(df[df['aggregated_rating'] >= 3.0]))
        }
    ]

    return facets
