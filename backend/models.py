from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """User model for authentication and personalization"""
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships with cascade delete
    folders = db.relationship('Folder', backref='user', lazy=True, cascade='all, delete-orphan')
    bookmarks = db.relationship('Bookmark', backref='user', lazy=True, cascade='all, delete-orphan')
    search_history = db.relationship('SearchHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    recipe_ratings = db.relationship('RecipeRating', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.user_id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Folder(db.Model):
    """Folder for organizing bookmarks"""
    __tablename__ = 'folders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ FIX: Remove backref to prevent circular reference when querying
    # User model already has 'folders' relationship

    # Relationships
    bookmarks = db.relationship('Bookmark', backref='folder', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'user_id': self.user_id,
            'bookmark_count': len(self.bookmarks),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Bookmark(db.Model):
    """Bookmark recipes into folders"""
    __tablename__ = 'bookmarks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    recipe_id = db.Column(db.Integer, nullable=False, index=True)  # Recipe ID from Elasticsearch
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True)
    recipe_name = db.Column(db.String(255), nullable=False)  # Changed: NOT NULL for better UX
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ FIX: Remove backref to prevent circular reference when querying
    # User model already has 'bookmarks' relationship

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'folder_id': self.folder_id,
            'recipe_id': self.recipe_id,
            'recipe_name': self.recipe_name or '',
            'notes': self.notes or '',
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class RecipeRating(db.Model):
    """User ratings for recipes (separate from bookmarks)"""
    __tablename__ = 'recipe_ratings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)  # แก้: users.id → users.user_id
    recipe_id = db.Column(db.Integer, nullable=False, index=True)
    recipe_name = db.Column(db.String(255), nullable=False)  # Cache recipe name
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    review = db.Column(db.Text, nullable=True)  # Optional text review
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Ensure one rating per recipe per user
    __table_args__ = (db.UniqueConstraint('user_id', 'recipe_id', name='unique_rating'),)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'recipe_id': self.recipe_id,
            'recipe_name': self.recipe_name,
            'rating': self.rating,
            'review': self.review,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class SearchHistory(db.Model):
    """User search history for personalization"""
    __tablename__ = 'search_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)  # แก้: users.id → users.user_id
    query = db.Column(db.String(500), nullable=False)
    results_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'query': self.query,
            'results_count': self.results_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
