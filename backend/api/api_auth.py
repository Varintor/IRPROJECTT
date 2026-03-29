"""
API-based authentication for React frontend
JSON API with token-based authentication
"""
from flask import Blueprint, request, jsonify
from models.models import db, User, Folder
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re
import secrets

api_auth_bp = Blueprint('api_auth', __name__)

# Simple token storage (in production, use Redis or database)
token_store = {}

def generate_token():
    """Generate secure token"""
    return secrets.token_hex(32)

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def require_auth(f):
    """Decorator to require authentication for API endpoints"""
    import time
    import logging
    logger = logging.getLogger(__name__)

    @wraps(f)
    def decorated_function(*args, **kwargs):
        start = time.time()
        logger.info(f"[AUTH] {request.method} {request.path} - Starting auth check")

        # Get token from header
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            logger.warning(f"[AUTH] No authorization header")
            return jsonify({'error': 'No authorization header'}), 401

        # Extract token (format: "Bearer <token>")
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            logger.warning(f"[AUTH] Invalid authorization format")
            return jsonify({'error': 'Invalid authorization format'}), 401

        logger.info(f"[AUTH] Token extracted, time: {time.time() - start:.3f}s")

        # Verify token
        if token not in token_store:
            logger.warning(f"[AUTH] Invalid token")
            return jsonify({'error': 'Invalid or expired token'}), 401

        logger.info(f"[AUTH] Token verified, time: {time.time() - start:.3f}s")

        # Get user from token
        user_id = token_store[token]
        logger.info(f"[AUTH] Fetching user {user_id} from database...")

        user = User.query.get(user_id)
        logger.info(f"[AUTH] User fetch took: {time.time() - start:.3f}s")

        if not user:
            logger.warning(f"[AUTH] User not found")
            return jsonify({'error': 'User not found'}), 401

        logger.info(f"[AUTH] Auth complete for user {user.username}, total time: {time.time() - start:.3f}s")

        # Store user in request context
        request.user = user
        return f(*args, **kwargs)

    return decorated_function

@api_auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """Register new user (JSON API)"""
    try:
        data = request.get_json()

        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        # Validation
        if not username or not email or not password:
            return jsonify({'error': 'Please fill in all fields'}), 400

        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400

        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400

        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400

        # Create user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        # Create default "Favorites" folder
        favorites = Folder(name='Favorites', user_id=user.user_id)
        db.session.add(favorites)
        db.session.commit()

        # Generate token
        token = generate_token()
        token_store[token] = user.user_id

        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict(),
            'token': token
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """Login user (JSON API)"""
    try:
        data = request.get_json()

        username_or_email = data.get('username', '').strip()
        password = data.get('password', '')

        if not username_or_email or not password:
            return jsonify({'error': 'Please provide username/email and password'}), 400

        # Try username first, then email
        user = User.query.filter_by(username=username_or_email).first()
        if not user:
            user = User.query.filter_by(email=username_or_email).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        if not check_password_hash(user.password_hash, password):
            return jsonify({'error': 'Invalid password'}), 401

        # Generate token
        token = generate_token()
        token_store[token] = user.user_id

        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'token': token
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_auth_bp.route('/api/logout', methods=['POST'])
@require_auth
def api_logout():
    """Logout user (JSON API)"""
    try:
        token = request.headers.get('Authorization', '').split(' ')[1]
        if token in token_store:
            del token_store[token]

        return jsonify({'message': 'Logout successful'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_auth_bp.route('/api/me', methods=['GET'])
@require_auth
def api_get_current_user():
    """Get current user info"""
    return jsonify({
        'user': request.user.to_dict()
    }), 200
