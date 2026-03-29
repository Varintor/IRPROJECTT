"""
API Blueprints
==============
Contains all Flask blueprints for API endpoints.
"""

from .api_auth import api_auth_bp
from .api_bookmarks import api_bookmarks_bp
from .api_recommendations import api_recommendations_bp

__all__ = ['api_auth_bp', 'api_bookmarks_bp', 'api_recommendations_bp']
