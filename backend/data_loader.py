"""
Shared data loader to avoid loading PKL file multiple times
"""
import sys
import os
from indexer_pkl import IndexerFromPKL

# Set UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Global singleton instance
_indexer = None
_documents = None

# Development mode: load smaller subset
DEV_MODE = os.getenv('DEV_MODE', 'true').lower() == 'true'
SAMPLE_SIZE = int(os.getenv('SAMPLE_SIZE', '10000'))  # Load 10K recipes in dev mode

def get_indexer():
    """Get or create the singleton indexer instance"""
    global _indexer
    if _indexer is None:
        print(f"Loading indexer (DEV_MODE={DEV_MODE}, SAMPLE_SIZE={SAMPLE_SIZE})...")
        _indexer = IndexerFromPKL()

        # Sample data in dev mode for faster loading
        if DEV_MODE and SAMPLE_SIZE < len(_indexer.documents):
            print(f"Sampling {SAMPLE_SIZE} recipes for development...")
            import pandas as pd
            _indexer.documents = _indexer.documents.sample(n=SAMPLE_SIZE, random_state=42).reset_index(drop=True)
            print(f"Sample loaded: {len(_indexer.documents)} recipes")

        print("Indexer loaded successfully!")
    return _indexer


def get_documents():
    """Get or create the documents DataFrame"""
    global _documents
    if _documents is None:
        indexer = get_indexer()
        _documents = indexer.documents.copy()
    return _documents
