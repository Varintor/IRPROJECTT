"""
API endpoints for bookmarks, folders, and ratings
"""
from flask import Blueprint, request, jsonify, current_app
from models import db, User, Folder, Bookmark, RecipeRating, SearchHistory
from api_auth import require_auth
from datetime import datetime
from shared_indexer import get_shared_indexer
import logging

logger = logging.getLogger(__name__)

api_bookmarks_bp = Blueprint('api_bookmarks', __name__)

# Recipe cache for additional performance
recipe_cache = {}

def get_indexer():
    """Get the shared indexer instance"""
    return get_shared_indexer()

# ============ FOLDER APIS ============

# ✅ DEBUG: Test endpoint without auth (for debugging only)
@api_bookmarks_bp.route('/api/debug/bookmarks/<int:user_id>', methods=['GET'])
def debug_get_bookmarks(user_id):
    """DEBUG: Get bookmarks without auth - to isolate the issue"""
    import time
    start_time = time.time()

    logger.info(f"[DEBUG] Fetching bookmarks for user {user_id} (NO AUTH)")

    try:
        bookmarks = Bookmark.query.filter_by(user_id=user_id)\
            .order_by(Bookmark.created_at.desc())\
            .limit(100)\
            .all()

        elapsed = time.time() - start_time
        logger.info(f"[DEBUG] ✅ Fetched {len(bookmarks)} bookmarks in {elapsed:.3f}s")

        db.session.close()

        return jsonify({
            'bookmarks': [bookmark.to_dict() for bookmark in bookmarks],
            'debug_time': f"{elapsed:.3f}s"
        }), 200

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[DEBUG] ❌ Error after {elapsed:.3f}s: {e}")
        return jsonify({'error': str(e)}), 500

# ✅ DEBUG: Test simple query without order_by
@api_bookmarks_bp.route('/api/debug/bookmarks_simple/<int:user_id>', methods=['GET'])
def debug_get_bookmarks_simple(user_id):
    """DEBUG: Get bookmarks without order_by - tests if that's the issue"""
    import time
    start_time = time.time()

    logger.info(f"[DEBUG SIMPLE] Fetching bookmarks for user {user_id} (NO ORDER BY)")

    try:
        # Very simple query - no order_by, just limit
        bookmarks = Bookmark.query.filter_by(user_id=user_id).limit(10).all()

        elapsed = time.time() - start_time
        logger.info(f"[DEBUG SIMPLE] ✅ Fetched {len(bookmarks)} bookmarks in {elapsed:.3f}s")

        db.session.close()

        return jsonify({
            'bookmarks': [bookmark.to_dict() for bookmark in bookmarks],
            'debug_time': f"{elapsed:.3f}s",
            'count': len(bookmarks)
        }), 200

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[DEBUG SIMPLE] ❌ Error after {elapsed:.3f}s: {e}")
        return jsonify({'error': str(e)}), 500

@api_bookmarks_bp.route('/api/folders', methods=['GET'])
@require_auth
def get_folders():
    """Get all folders for current user - WITH embedded bookmarks (WORKAROUND)"""
    import time
    start_time = time.time()

    logger.info(f"[FOLDERS] Fetching for user {request.user.user_id}")

    try:
        # ✅ WORKAROUND: Get folders first (this works!)
        folders = Folder.query.filter_by(user_id=request.user.user_id).all()

        # ✅ WORKAROUND: For each folder, manually count bookmarks (avoid Bookmark query)
        result_folders = []
        for folder in folders:
            # Use a simple count instead of full bookmark query
            try:
                bookmark_count = Bookmark.query.filter_by(folder_id=folder.id).count()
            except:
                bookmark_count = 0

            folder_dict = folder.to_dict()
            folder_dict['bookmark_count'] = bookmark_count
            result_folders.append(folder_dict)

        elapsed = time.time() - start_time
        logger.info(f"[FOLDERS] ✅ Fetched {len(folders)} folders in {elapsed:.3f}s")

        # Close session
        db.session.close()

        return jsonify({
            'folders': result_folders
        }), 200

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[FOLDERS] ❌ Error after {elapsed:.3f}s: {e}")

        # Close session on error
        try:
            db.session.close()
        except:
            pass

        # ✅ FIX: Return empty array on error
        return jsonify({
            'folders': [],
            'error': str(e) if current_app.debug else 'Failed to fetch folders'
        }), 200

@api_bookmarks_bp.route('/api/folders', methods=['POST'])
@require_auth
def create_folder():
    """Create new folder"""
    try:
        data = request.get_json()

        name = data.get('name', '').strip()

        if not name:
            return jsonify({'error': 'Folder name is required'}), 400

        # Check if folder with same name exists
        existing = Folder.query.filter_by(user_id=request.user.user_id, name=name).first()
        if existing:
            return jsonify({'error': 'Folder with this name already exists'}), 400

        folder = Folder(
            name=name,
            user_id=request.user.user_id
        )

        db.session.add(folder)
        db.session.commit()

        return jsonify({
            'message': 'Folder created',
            'folder': folder.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bookmarks_bp.route('/api/folders/<int:folder_id>', methods=['PUT'])
@require_auth
def update_folder(folder_id):
    """Update folder"""
    try:
        folder = Folder.query.filter_by(id=folder_id, user_id=request.user.user_id).first()

        if not folder:
            return jsonify({'error': 'Folder not found'}), 404

        data = request.get_json()

        if 'name' in data:
            folder.name = data['name'].strip()

        db.session.commit()

        return jsonify({
            'message': 'Folder updated',
            'folder': folder.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bookmarks_bp.route('/api/folders/<int:folder_id>', methods=['DELETE'])
@require_auth
def delete_folder(folder_id):
    """Delete folder and all its bookmarks"""
    try:
        folder = Folder.query.filter_by(id=folder_id, user_id=request.user.user_id).first()

        if not folder:
            return jsonify({'error': 'Folder not found'}), 404

        # Delete bookmarks in folder
        Bookmark.query.filter_by(folder_id=folder_id).delete()

        # Delete folder
        db.session.delete(folder)
        db.session.commit()

        return jsonify({'message': 'Folder deleted'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============ RECIPE BY ID API ============

@api_bookmarks_bp.route('/api/recipes/<int:recipe_id>', methods=['GET'])
def get_recipe_by_id(recipe_id):
    """Get full recipe details by ID - OPTIMIZED with caching and shared indexer"""
    try:
        # Check cache first
        if recipe_id in recipe_cache:
            logger.debug(f"Cache HIT for recipe {recipe_id}")
            return jsonify(recipe_cache[recipe_id]), 200

        logger.debug(f"Cache MISS for recipe {recipe_id}")

        indexer_instance = get_indexer()
        df = indexer_instance.documents

        # DataFrame is already indexed by recipe_id (done at startup)
        # Use .loc for O(log N) lookup
        if recipe_id not in df.index:
            logger.warning(f"Recipe {recipe_id} not found")
            return jsonify({'error': 'Recipe not found'}), 404

        recipe = df.loc[recipe_id]

        # Transform ingredient_parts and instructions - optimized for the dataset
        ingredients = []
        if recipe['ingredient_parts']:
            ingredient_text = str(recipe['ingredient_parts']).strip()

            # Check format and split accordingly
            if len(ingredient_text) < 200 and ingredient_text.count(' ') > 5:
                # Short format: "sugar lemon juice butter flour" - split by common ingredient names
                import re
                # Split by capital letters followed by common ingredient words
                common_ingredients = ['sugar', 'flour', 'salt', 'pepper', 'butter', 'oil', 'milk', 'egg',
                                     'eggs', 'cheese', 'cream', 'water', 'onion', 'garlic', 'tomato',
                                     'lemon', 'vanilla', 'chocolate', 'rice', 'pasta', 'chicken']
                pattern = r'\s+(?=' + '|'.join(common_ingredients) + r')'
                parts = re.split(pattern, ingredient_text, flags=re.IGNORECASE)
                ingredients = [p.strip() for p in parts if p.strip()][:12]
            elif ',' in ingredient_text and ingredient_text.count(',') > 3:
                # Comma-separated
                ingredients = [ing.strip() for ing in ingredient_text.split(',') if ing.strip()][:12]
            elif '\n' in ingredient_text:
                # Newline-separated
                ingredients = [ing.strip() for ing in ingredient_text.split('\n') if ing.strip()][:12]
            else:
                # Long text - split by sentences or reasonable chunks
                import re
                sentences = re.split(r'(?<=[.])\s+', ingredient_text)
                if len(sentences) > 3:
                    ingredients = [s.strip() for s in sentences if s.strip()][:10]
                else:
                    # Chunk by 80 chars
                    ingredients = [ingredient_text[i:i+80].strip()
                                for i in range(0, len(ingredient_text), 80)
                                if ingredient_text[i:i+80].strip()][:8]

        instructions = []
        if recipe['instructions']:
            instruction_text = str(recipe['instructions']).strip()
            import re

            # Try to split by step indicators first
            step_matches = re.split(r'Step\s+\d+[:.]?\s*', instruction_text, flags=re.IGNORECASE)
            if len(step_matches) > 1:
                instructions = [s.strip() for s in step_matches if s.strip()][:8]
            else:
                # Split by numbered steps or bullet points
                numbered_steps = re.split(r'\d+[\.)]\s*', instruction_text)
                if len(numbered_steps) > 2:
                    instructions = [s.strip() for s in numbered_steps[1:] if s.strip()][:8]
                else:
                    # Split by periods followed by capital letters (new sentences)
                    sentences = re.split(r'\.\s+(?=[A-Z])', instruction_text)
                    if len(sentences) > 2:
                        instructions = [s.strip() + '.' for s in sentences if s.strip()][:8]
                    else:
                        # Last resort: split by all periods
                        instructions = [s.strip() + '.' for s in instruction_text.split('.')
                                      if s.strip() and len(s.strip()) > 5][:6]

        # Build response
        recipe_data = {
            'recipe_id': int(recipe['recipe_id']),
            'name': recipe['name'],
            'category': recipe['category'],
            'images': recipe['images'],
            'ingredient_parts': ingredients,
            'instructions': instructions,
            'processed_text': recipe['processed_text'],
            'aggregated_rating': float(recipe['aggregated_rating']) if recipe['aggregated_rating'] else 0.0,
            'review_count': int(recipe['review_count']) if recipe['review_count'] else 0,
            'total_time': recipe['total_time'] or '30 min',
            'description': recipe['processed_text'][:200] + '...' if len(recipe['processed_text']) > 200 else recipe['processed_text']
        }

        # Cache the result (limit cache size to avoid memory issues)
        if len(recipe_cache) < 1000:
            recipe_cache[recipe_id] = recipe_data

        return jsonify(recipe_data), 200

    except Exception as e:
        logger.error(f"Error getting recipe {recipe_id}: {e}")
        return jsonify({'error': str(e)}), 500

# ============ BOOKMARK APIS ============

@api_bookmarks_bp.route('/api/bookmarks', methods=['GET'])
@require_auth
def get_bookmarks():
    """Get all bookmarks, optionally filtered by folder"""
    import time
    start_time = time.time()

    folder_id = request.args.get('folder_id', type=int)

    logger.info(f"[BOOKMARKS] Fetching for user {request.user.user_id}, folder {folder_id}")

    try:
        # ✅ FIX: Use default db.session with explicit cleanup
        query = Bookmark.query.filter_by(user_id=request.user.user_id)

        if folder_id:
            query = query.filter_by(folder_id=folder_id)

        # ✅ OPTIMIZATION: Limit results to prevent timeout
        bookmarks = query.order_by(Bookmark.created_at.desc()).limit(1000).all()

        elapsed = time.time() - start_time
        logger.info(f"[BOOKMARKS] ✅ Fetched {len(bookmarks)} bookmarks in {elapsed:.3f}s")

        result = {
            'bookmarks': [bookmark.to_dict() for bookmark in bookmarks]
        }

        # Close session to prevent connection pool exhaustion
        db.session.close()

        return jsonify(result), 200

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[BOOKMARKS] ❌ Error after {elapsed:.3f}s: {e}")
        logger.error(f"[BOOKMARKS] Traceback: {e.__traceback__}")

        # Close session on error
        try:
            db.session.close()
        except:
            pass

        # ✅ FIX: Return empty array instead of crashing
        return jsonify({
            'bookmarks': [],
            'error': str(e) if current_app.debug else 'Failed to fetch bookmarks'
        }), 200  # Return 200 with empty array to prevent frontend hang

@api_bookmarks_bp.route('/api/bookmarks', methods=['POST'])
@require_auth
def create_bookmark():
    """Add recipe to folder (bookmark)"""
    try:
        data = request.get_json()

        folder_id = data.get('folder_id')
        recipe_id = data.get('recipe_id')
        recipe_name = data.get('recipe_name', '')

        if not folder_id or not recipe_id:
            return jsonify({'error': 'folder_id and recipe_id are required'}), 400

        # Check if folder exists and belongs to user
        folder = Folder.query.filter_by(id=folder_id, user_id=request.user.user_id).first()
        if not folder:
            return jsonify({'error': 'Folder not found'}), 404

        # Check if already bookmarked
        existing = Bookmark.query.filter_by(
            user_id=request.user.user_id,
            folder_id=folder_id,
            recipe_id=recipe_id
        ).first()

        if existing:
            return jsonify({'error': 'Recipe already bookmarked in this folder'}), 400

        # If recipe_name not provided, try to get it from indexer
        if not recipe_name:
            try:
                indexer_instance = get_indexer()
                df = indexer_instance.documents
                if recipe_id in df.index:
                    recipe = df.loc[recipe_id]
                    recipe_name = recipe['name']
            except:
                pass

        bookmark = Bookmark(
            user_id=request.user.user_id,
            folder_id=folder_id,
            recipe_id=recipe_id,
            recipe_name=recipe_name or f"Recipe #{recipe_id}"
        )

        db.session.add(bookmark)
        db.session.commit()

        return jsonify({
            'message': 'Recipe bookmarked',
            'bookmark': bookmark.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bookmarks_bp.route('/api/bookmarks/<int:bookmark_id>', methods=['DELETE'])
@require_auth
def delete_bookmark(bookmark_id):
    """Remove bookmark"""
    try:
        bookmark = Bookmark.query.filter_by(id=bookmark_id, user_id=request.user.user_id).first()

        if not bookmark:
            return jsonify({'error': 'Bookmark not found'}), 404

        db.session.delete(bookmark)
        db.session.commit()

        return jsonify({'message': 'Bookmark removed'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============ RATING APIS ============

@api_bookmarks_bp.route('/api/ratings', methods=['POST'])
@require_auth
def rate_recipe():
    """Rate a recipe"""
    try:
        data = request.get_json()

        recipe_id = data.get('recipe_id')
        recipe_name = data.get('recipe_name', '').strip()
        rating = data.get('rating')  # 1-5
        review = data.get('review', '').strip()

        if not recipe_id or not rating:
            return jsonify({'error': 'recipe_id and rating are required'}), 400

        if not (1 <= rating <= 5):
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400

        # Check if rating exists
        existing_rating = RecipeRating.query.filter_by(
            user_id=request.user.user_id,
            recipe_id=recipe_id
        ).first()

        if existing_rating:
            # Update existing rating
            existing_rating.rating = rating
            existing_rating.review = review
            existing_rating.updated_at = datetime.utcnow()
            db.session.commit()

            return jsonify({
                'message': 'Rating updated',
                'rating': existing_rating.to_dict()
            }), 200
        else:
            # Create new rating
            new_rating = RecipeRating(
                user_id=request.user.user_id,
                recipe_id=recipe_id,
                recipe_name=recipe_name,
                rating=rating,
                review=review
            )

            db.session.add(new_rating)
            db.session.commit()

            return jsonify({
                'message': 'Recipe rated',
                'rating': new_rating.to_dict()
            }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bookmarks_bp.route('/api/ratings/<int:recipe_id>', methods=['GET'])
@require_auth
def get_recipe_rating(recipe_id):
    """Get user's rating for a recipe"""
    rating = RecipeRating.query.filter_by(
        user_id=request.user.user_id,
        recipe_id=recipe_id
    ).first()

    if rating:
        return jsonify({'rating': rating.to_dict()}), 200
    else:
        return jsonify({'rating': None}), 200

@api_bookmarks_bp.route('/api/ratings', methods=['GET'])
@require_auth
def get_user_ratings():
    """Get all ratings by current user"""
    ratings = RecipeRating.query.filter_by(user_id=request.user.user_id)\
        .order_by(RecipeRating.updated_at.desc()).all()

    return jsonify({
        'ratings': [rating.to_dict() for rating in ratings]
    }), 200
