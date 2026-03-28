import os
from pathlib import Path
import pandas as pd


class Indexer_manual:
    def __init__(self, csv_filename="resources/recipes_final_for_search.csv"):
        current_dir = Path(os.path.abspath(""))

        self.data_file = current_dir / csv_filename
        if not self.data_file.exists():
            self.data_file = current_dir.parent / csv_filename

        print(f"Looking for CSV file at: {self.data_file}")
        print(f"File exists: {self.data_file.exists()}")

        if not self.data_file.exists():
            raise FileNotFoundError(f"Cannot find {csv_filename}")

        self.run_indexer()

    def run_indexer(self):
        print("Loading CSV...")
        self.documents = pd.read_csv(self.data_file)

        required_cols = ["recipe_id", "name", "category", "processed_text"]
        missing_cols = [col for col in required_cols if col not in self.documents.columns]
        if missing_cols:
            raise ValueError(f"Missing columns in CSV: {missing_cols}")

        self.documents["recipe_id"] = pd.to_numeric(
            self.documents["recipe_id"], errors="coerce"
        ).fillna(0).astype(int)

        self.documents["name"] = self.documents["name"].fillna("").astype(str)
        self.documents["category"] = self.documents["category"].fillna("").astype(str)
        self.documents["processed_text"] = self.documents["processed_text"].fillna("").astype(str)


if __name__ == "__main__":
    indexer = Indexer_manual()
    print(indexer.documents.head())