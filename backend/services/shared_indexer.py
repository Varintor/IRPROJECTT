"""
Shared indexer singleton - preload once, use everywhere
This prevents loading the PKL file multiple times
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.indexer_pkl import IndexerFromPKL
import logging

logger = logging.getLogger(__name__)

# Shared global instance
_shared_indexer = None
_is_loaded = False

def get_shared_indexer():
    """Get the shared indexer instance"""
    global _shared_indexer, _is_loaded
    if not _is_loaded:
        logger.info("="*60)
        logger.info("🔄 INITIALIZING SHARED INDEXER...")
        logger.info("="*60)
        _shared_indexer = IndexerFromPKL()
        _is_loaded = True

        # Optimize DataFrame for fast lookups
        logger.info("📊 Optimizing DataFrame for fast lookups...")
        df = _shared_indexer.documents

        # Set index by recipe_id for O(log N) lookups
        if not hasattr(df, '_indexed_by_id'):
            logger.info("Setting DataFrame index by recipe_id...")
            df.set_index('recipe_id', inplace=True, drop=False)
            df._indexed_by_id = True
            logger.info("✅ DataFrame indexed by recipe_id")

        logger.info(f"✅ Shared indexer ready: {len(_shared_indexer.documents)} recipes")
        logger.info("="*60)
    return _shared_indexer

def preload_indexer():
    """Force preload indexer (call at Flask startup)"""
    get_shared_indexer()

def is_indexer_loaded():
    """Check if indexer has been loaded"""
    return _is_loaded
