"""
Shared data loader - now uses shared_indexer to avoid loading PKL file multiple times
"""
import sys
import os

# Set UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Global documents cache
_documents = None

def get_documents():
    """Get or create the documents DataFrame (using shared indexer)"""
    global _documents
    if _documents is None:
        from services.shared_indexer import get_shared_indexer
        indexer = get_shared_indexer()
        _documents = indexer.documents.copy()
    return _documents
