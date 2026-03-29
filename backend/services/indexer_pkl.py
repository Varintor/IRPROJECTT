import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import pickle

# Set UTF-8 encoding for stdout (handles Thai characters in paths)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


class IndexerFromPKL:
    """Load data from cleaned_ready_for_es.pkl instead of CSV"""

    def __init__(self, pkl_filename="../cleaned_ready_for_es.pkl"):
        current_dir = Path(os.path.abspath(""))

        self.pkl_file = current_dir / pkl_filename

        print(f"Looking for PKL file at: {self.pkl_file}")
        print(f"File exists: {self.pkl_file.exists()}")

        if not self.pkl_file.exists():
            # Try parent directory
            self.pkl_file = current_dir.parent / pkl_filename
            print(f"Trying parent: {self.pkl_file}")
            print(f"File exists: {self.pkl_file.exists()}")

        if not self.pkl_file.exists():
            raise FileNotFoundError(f"Cannot find {pkl_filename}")

        self.run_indexer()

    def run_indexer(self):
        print("Loading PKL file...")
        try:
            # Try pandas read_pickle first (handles pyarrow serialization)
            self.documents = pd.read_pickle(self.pkl_file)
        except Exception as e:
            print(f"Pandas read_pickle failed: {e}")
            print("Trying standard pickle.load...")
            with open(self.pkl_file, 'rb') as f:
                self.documents = pickle.load(f)

        print(f"Loaded {len(self.documents)} recipes")

        # Rename columns from PascalCase to snake_case (เหมือน index "recipes")
        print("Renaming columns from PascalCase to snake_case...")
        self.documents = self.documents.rename(columns={
            'RecipeId': 'recipe_id',
            'Name': 'name',
            'RecipeCategory': 'category',
            'RecipeInstructions': 'instructions',
            'RecipeIngredientParts': 'ingredient_parts',
            'AggregatedRating': 'aggregated_rating',
            'ReviewCount': 'review_count',
            'RecipeYield': 'recipe_yield',
            'TotalTime': 'total_time',
        })

        # Create processed_text field from cleaned columns
        print("Creating processed_text field...")
        self.documents['processed_text'] = (
            self.documents['Name_clean'].fillna('') + ' ' +
            self.documents['RecipeIngredientParts_clean'].fillna('') + ' ' +
            self.documents['RecipeInstructions_clean'].fillna('')
        )

        # Convert recipe_id to integer
        self.documents["recipe_id"] = pd.to_numeric(
            self.documents["recipe_id"], errors="coerce"
        ).fillna(0).astype(int)

        # Fill missing values
        self.documents["name"] = self.documents["name"].fillna("")
        self.documents["category"] = self.documents["category"].fillna("")
        self.documents["processed_text"] = self.documents["processed_text"].fillna("")

        # Handle images
        if 'Images' in self.documents.columns:
            self.documents["images"] = self.documents["Images"].fillna("")
        else:
            self.documents["images"] = ""

        # Handle instructions
        if 'instructions' in self.documents.columns:
            self.documents["instructions"] = self.documents["instructions"].fillna("")
        else:
            self.documents["instructions"] = ""

        # Handle ingredient_parts
        if 'ingredient_parts' in self.documents.columns:
            self.documents["ingredient_parts"] = self.documents["ingredient_parts"].fillna("")
        else:
            self.documents["ingredient_parts"] = ""

        # Handle total_time
        if 'total_time' in self.documents.columns:
            self.documents["total_time"] = self.documents["total_time"].fillna("30 min")
        else:
            self.documents["total_time"] = "30 min"

        # Select only required columns (snake_case)
        required_cols = [
            "recipe_id", "name", "category", "processed_text",
            "images", "ingredient_parts", "instructions",
            "aggregated_rating", "review_count", "total_time"
        ]

        # Check which columns exist
        available_cols = [col for col in required_cols if col in self.documents.columns]
        self.documents = self.documents[available_cols]

        print(f"Final columns ({len(self.documents.columns)}): {list(self.documents.columns)}")

        # Show sample
        print("\nSample recipe:")
        print(f"  recipe_id: {self.documents['recipe_id'].iloc[0]}")
        print(f"  name: {self.documents['name'].iloc[0]}")
        print(f"  category: {self.documents['category'].iloc[0]}")
        if 'aggregated_rating' in self.documents.columns:
            print(f"  rating: {self.documents['aggregated_rating'].iloc[0]}")
        print(f"  processed_text: {self.documents['processed_text'].iloc[0][:100]}...")


if __name__ == "__main__":
    indexer = IndexerFromPKL()
    print(f"\nTotal recipes ready: {len(indexer.documents)}")
    print(f"Columns: {list(indexer.documents.columns)}")
