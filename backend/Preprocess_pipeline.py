import ast
import math
import re
import string
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from nltk.stem import PorterStemmer
from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors


# -------------------------
# GLOBALS
# -------------------------
TOKEN_RE = re.compile(r"[a-zA-Z]+")
WHITESPACE_RE = re.compile(r"\s+")
PUNCT_TABLE = str.maketrans("", "", string.punctuation + "“”‘’" + u"\xa0")
STEMMER = PorterStemmer()


# -------------------------
# SMALL HELPERS
# -------------------------
def chunkify(seq: Sequence, n_chunks: int) -> List[Sequence]:
    n = len(seq)
    if n == 0:
        return []
    if n_chunks <= 0:
        n_chunks = 1

    chunk_size = math.ceil(n / n_chunks)
    return [seq[i:i + chunk_size] for i in range(0, n, chunk_size)]


def tokenize_fast(text: str) -> List[str]:
    if not text:
        return []
    return TOKEN_RE.findall(str(text).lower())


# -------------------------
# PARSERS
# -------------------------
def clean_r_c_format(x):
    """
    Convert R-style c("a", "b") into Python list.
    Leave other values as-is.
    """
    if pd.isna(x):
        return ""

    if isinstance(x, list):
        return x

    x = str(x).strip()

    if x.startswith("c(") and x.endswith(")"):
        inner = x[2:-1].strip()
        if inner == "":
            return []

        try:
            parsed = ast.literal_eval("[" + inner + "]")
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

        return [p.strip().strip('"').strip("'") for p in inner.split(",")]

    return x


def parse_list_column(x) -> str:
    """
    Convert Python/R-like list payloads into a space-joined string.
    """
    if isinstance(x, list):
        return " ".join(map(str, x))

    if pd.isna(x):
        return ""

    x = str(x).strip()

    try:
        parsed = ast.literal_eval(x)
        if isinstance(parsed, list):
            return " ".join(map(str, parsed))
    except Exception:
        pass

    return x


# -------------------------
# TEXT CLEANING
# -------------------------
def clean_text_basic(s) -> str:
    if pd.isna(s):
        return ""

    s = str(s)
    s = s.lower()
    s = s.replace("quote unquote", " ")
    s = s.replace("_long_variable_name", " ")
    s = s.translate(PUNCT_TABLE)
    s = WHITESPACE_RE.sub(" ", s).strip()
    return s


def normalize_name(text: str) -> str:
    if pd.isna(text):
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


# -------------------------
# IMAGE CLEANING
# -------------------------
def clean_image_value(x) -> str:
    """
    Normalize image field into a single URL string or empty string.
    Handles:
    - plain URL
    - "URL"
    - c("URL1","URL2")
    - ["URL1", "URL2"]
    - character(0)
    - empty / nan
    """
    if pd.isna(x):
        return ""

    if isinstance(x, list):
        vals = [str(v).strip().strip('"').strip("'") for v in x if str(v).strip()]
        vals = [v for v in vals if v.startswith(("http://", "https://"))]
        return vals[0] if vals else ""

    x = str(x).strip()
    if x == "" or x.lower() in {"nan", "none", "null", "character(0)"}:
        return ""

    if x.startswith("c(") and x.endswith(")"):
        inner = x[2:-1].strip()
        if inner == "":
            return ""
        try:
            parsed = ast.literal_eval("[" + inner + "]")
            if isinstance(parsed, list):
                vals = [str(v).strip().strip('"').strip("'") for v in parsed if str(v).strip()]
                vals = [v for v in vals if v.startswith(("http://", "https://"))]
                return vals[0] if vals else ""
        except Exception:
            parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
            parts = [p for p in parts if p.startswith(("http://", "https://"))]
            return parts[0] if parts else ""

    try:
        parsed = ast.literal_eval(x)
        if isinstance(parsed, list):
            vals = [str(v).strip().strip('"').strip("'") for v in parsed if str(v).strip()]
            vals = [v for v in vals if v.startswith(("http://", "https://"))]
            return vals[0] if vals else ""
    except Exception:
        pass

    x = x.strip('"').strip("'")
    return x if x.startswith(("http://", "https://")) else ""


# -------------------------
# IMAGE FILLING BY SIMILAR NAME
# -------------------------
def fill_missing_recipe_images_knn(
    df: pd.DataFrame,
    name_col: str = "name",
    image_col: str = "images",
    ngram_range: Tuple[int, int] = (3, 5),
    chunk_size: int = 50000,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Fill missing images using the nearest recipe name.
    Always assigns the nearest match if a reference row exists.
    """
    df = df.copy()

    if name_col not in df.columns or image_col not in df.columns:
        raise KeyError(f"DataFrame must contain columns: {name_col}, {image_col}")

    df[image_col] = df[image_col].apply(clean_image_value)
    df["_name_clean"] = df[name_col].apply(normalize_name)

    has_image_mask = df[image_col].astype(str).str.strip() != ""
    missing_image_mask = ~has_image_mask

    ref_df = df.loc[has_image_mask, ["_name_clean", image_col]].copy()
    miss_df = df.loc[missing_image_mask, ["_name_clean"]].copy()

    miss_nonempty_mask = miss_df["_name_clean"].astype(str).str.strip() != ""
    miss_df_nonempty = miss_df.loc[miss_nonempty_mask].copy()

    if verbose:
        print(f"Rows with image    : {len(ref_df):,}")
        print(f"Rows missing image : {missing_image_mask.sum():,}")
        print(f"Missing with name  : {len(miss_df_nonempty):,}")

    if len(ref_df) == 0:
        raise ValueError("No reference rows with images found.")

    ref_df = ref_df.drop_duplicates(subset=["_name_clean"]).reset_index(drop=True)
    ref_names = ref_df["_name_clean"].tolist()
    ref_images = ref_df[image_col].tolist()

    if verbose:
        print("Building TF-IDF vectors for image matching...")

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=ngram_range)
    X_ref = vectorizer.fit_transform(ref_names)

    nn = NearestNeighbors(n_neighbors=1, metric="cosine")
    nn.fit(X_ref)

    if "matched_name" not in df.columns:
        df["matched_name"] = None
    if "matched_score" not in df.columns:
        df["matched_score"] = 0.0

    missing_indices = miss_df_nonempty.index.to_list()
    missing_names = miss_df_nonempty["_name_clean"].tolist()

    for start in range(0, len(missing_names), chunk_size):
        end = min(start + chunk_size, len(missing_names))
        chunk_names = missing_names[start:end]
        chunk_indices = missing_indices[start:end]

        X_chunk = vectorizer.transform(chunk_names)
        distances, indices = nn.kneighbors(X_chunk, n_neighbors=1)

        distances = distances.ravel()
        indices = indices.ravel()
        similarities = 1.0 - distances

        for row_idx, ref_idx, sim in zip(chunk_indices, indices, similarities):
            df.at[row_idx, image_col] = ref_images[ref_idx]
            df.at[row_idx, "matched_name"] = ref_names[ref_idx]
            df.at[row_idx, "matched_score"] = float(sim)

        if verbose:
            print(f"  processed {end:,}/{len(missing_names):,}")

    df[image_col] = df[image_col].fillna("").astype(str).str.strip()
    return df.drop(columns=["_name_clean"])


# -------------------------
# DATAFRAME CLEANING
# -------------------------
def clean_recipes(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    """
    Clean text + image together and return one normalized dataframe.
    This is the main function you want before search indexing.
    """
    t0 = time.time()
    df = df.copy()

    keep_cols = [
        "RecipeId",
        "Name",
        "Description",
        "RecipeCategory",
        "Keywords",
        "RecipeIngredientParts",
        "RecipeInstructions",
        "Images",
    ]
    df = df[[c for c in keep_cols if c in df.columns]].copy()

    df = df.rename(columns={
        "RecipeId": "recipe_id",
        "Name": "name",
        "Description": "description",
        "RecipeCategory": "category",
        "Keywords": "keywords",
        "RecipeIngredientParts": "ingredient_parts",
        "RecipeInstructions": "instructions",
        "Images": "images",
    })

    expected_cols = [
        "recipe_id",
        "name",
        "description",
        "category",
        "keywords",
        "ingredient_parts",
        "instructions",
        "images",
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    # preserve ID and image separately from text cleaning
    df["recipe_id"] = df["recipe_id"].astype(str).str.strip()
    df["name"] = df["name"].fillna("").astype(str).str.strip()
    df["images"] = df["images"].apply(clean_image_value)

    list_like_text_cols = ["keywords", "ingredient_parts", "instructions"]
    for col in list_like_text_cols:
        df[col] = df[col].apply(clean_r_c_format)
        df[col] = df[col].apply(parse_list_column)

    text_cols = ["name", "description", "category", "keywords", "ingredient_parts", "instructions"]
    for col in text_cols:
        df[col] = df[col].fillna("")
        df[col] = df[col].apply(clean_text_basic)

    df = df[df["recipe_id"] != ""].copy()
    df = df[df["name"] != ""].copy()
    df = df.drop_duplicates(subset=["recipe_id"]).copy()

    df["search_text"] = (
        df["name"] + " "
        + df["description"] + " "
        + df["ingredient_parts"] + " "
        + df["instructions"] + " "
        + df["keywords"] + " "
        + df["category"]
    ).apply(lambda s: WHITESPACE_RE.sub(" ", str(s)).strip())

    if verbose:
        print(f"  - clean_recipes done in {time.time() - t0:.2f} sec")
        print(f"  - rows kept        : {len(df):,}")
        print(f"  - empty images     : {(df['images'] == '').sum():,}")
        print(f"  - empty search_text: {(df['search_text'] == '').sum():,}")

    return df


# -------------------------
# STEM CACHE
# -------------------------
def create_stem_cache(
    df: pd.DataFrame,
    text_cols: Optional[Iterable[str]] = None,
    verbose: bool = False,
) -> dict:
    t0 = time.time()

    if text_cols is None:
        text_cols = ["name", "description", "ingredient_parts", "instructions", "keywords", "category"]

    vocab = set()
    for col in text_cols:
        if col in df.columns:
            for text in df[col].fillna("").astype(str):
                vocab.update(tokenize_fast(text))

    stem_cache = {tok: STEMMER.stem(tok) for tok in vocab}

    if verbose:
        print(f"  - create_stem_cache done in {time.time() - t0:.2f} sec | vocab={len(stem_cache):,}")

    return stem_cache


# -------------------------
# PREPROCESS SINGLE TEXT
# -------------------------
def preprocess_single_text(text, stop_dict: set, stem_cache: dict) -> str:
    if pd.isna(text):
        return ""

    tokens = tokenize_fast(str(text))
    tokens = [t for t in tokens if len(t) > 2 and t not in stop_dict]
    tokens = [stem_cache.get(t, STEMMER.stem(t)) for t in tokens]
    return " ".join(tokens)


# -------------------------
# SEQUENTIAL PREPROCESS
# -------------------------
def preprocess_series(
    text_series: pd.Series,
    stop_dict: set,
    stem_cache: dict,
    verbose: bool = False,
    every: int = 10000,
) -> pd.Series:
    t0 = time.time()

    texts = text_series.fillna("").astype(str).tolist()
    processed = []

    for i, text in enumerate(texts, start=1):
        processed.append(preprocess_single_text(text, stop_dict, stem_cache))
        if verbose and every > 0 and i % every == 0:
            print(f"  - processed {i:,}/{len(texts):,} rows")

    if verbose:
        print(f"  - preprocess_series done in {time.time() - t0:.2f} sec")

    return pd.Series(processed, index=text_series.index)


# -------------------------
# PARALLEL PREPROCESS
# -------------------------
def _process_chunk(text_list: Sequence[str], stop_dict: set, stem_cache: dict) -> List[str]:
    return [preprocess_single_text(text, stop_dict, stem_cache) for text in text_list]


def preprocess_series_parallel(
    text_series: pd.Series,
    stop_dict: set,
    stem_cache: dict,
    n_jobs: int = 2,
    verbose: bool = False,
) -> pd.Series:
    t0 = time.time()

    texts = text_series.fillna("").astype(str).tolist()
    if len(texts) == 0:
        return pd.Series([], index=text_series.index, dtype="object")

    if n_jobs is None or n_jobs <= 1:
        return preprocess_series(text_series, stop_dict, stem_cache, verbose=verbose)

    chunks = chunkify(texts, n_jobs)

    results: List[str] = []
    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = [executor.submit(_process_chunk, chunk, stop_dict, stem_cache) for chunk in chunks]
        for future in futures:
            results.extend(future.result())

    if verbose:
        print(f"  - preprocess_series_parallel done in {time.time() - t0:.2f} sec")

    return pd.Series(results, index=text_series.index)


# -------------------------
# FULL PIPELINE
# -------------------------
def prepare_recipes_for_ir(
    recipes: pd.DataFrame,
    stop_dict: set,
    use_parallel: bool = True,
    n_jobs: int = 4,
    fill_missing_images: bool = False,
    verbose: bool = True,
):
    """
    Full pipeline:
    1) clean text + images together
    2) optionally fill missing images from similar recipe names
    3) build processed_text
    Returns a single dataframe ready for search/indexing.
    """
    t0 = time.time()
    df = recipes.copy()

    if verbose:
        print("[1/3] Cleaning dataframe...")
    cleaned_df = clean_recipes(df, verbose=False)

    if fill_missing_images and "images" in cleaned_df.columns:
        if verbose:
            print("[2/3] Filling missing images from similar recipe names...")
        cleaned_df = fill_missing_recipe_images_knn(
            cleaned_df,
            name_col="name",
            image_col="images",
            verbose=verbose,
        )
        step_label = "[3/3]"
    else:
        step_label = "[2/2]"

    if verbose:
        print(f"    rows={len(cleaned_df):,}")
        print(f"    empty search_text = {(cleaned_df['search_text'] == '').sum():,}")
        print(f"    empty images      = {(cleaned_df['images'] == '').sum():,}")
        print("Building stem cache...")

    stem_cache = create_stem_cache(cleaned_df, verbose=False)

    if verbose:
        print(f"    vocab={len(stem_cache):,}")
        print(f"{step_label} Preprocessing search_text...")

    if use_parallel:
        cleaned_df["processed_text"] = preprocess_series_parallel(
            cleaned_df["search_text"],
            stop_dict,
            stem_cache,
            n_jobs=n_jobs,
            verbose=verbose,
        )
    else:
        cleaned_df["processed_text"] = preprocess_series(
            cleaned_df["search_text"],
            stop_dict,
            stem_cache,
            verbose=verbose,
        )

    final_cols = [
        "recipe_id",
        "name",
        "description",
        "category",
        "keywords",
        "ingredient_parts",
        "instructions",
        "images",
        "search_text",
        "processed_text",
    ]
    final_cols = [c for c in final_cols if c in cleaned_df.columns]
    cleaned_df = cleaned_df[final_cols].copy()

    if verbose:
        print(f"    empty processed_text = {(cleaned_df['processed_text'] == '').sum():,}")
        print(f"[DONE] total time = {time.time() - t0:.2f} sec")

    return cleaned_df, stem_cache


# -------------------------
# SAVE HELPER
# -------------------------
def prepare_and_save_recipes_for_ir(
    recipes: pd.DataFrame,
    stop_dict: set,
    output_csv: str = "recipes_final_for_search.csv",
    use_parallel: bool = True,
    n_jobs: int = 4,
    fill_missing_images: bool = False,
    verbose: bool = True,
):
    cleaned_df, stem_cache = prepare_recipes_for_ir(
        recipes=recipes,
        stop_dict=stop_dict,
        use_parallel=use_parallel,
        n_jobs=n_jobs,
        fill_missing_images=fill_missing_images,
        verbose=verbose,
    )
    cleaned_df.to_csv(output_csv, index=False)

    if verbose:
        print(f"Saved cleaned file to: {output_csv}")

    return cleaned_df, stem_cache


# -------------------------
# OPTIONAL EXAMPLE
# -------------------------
if __name__ == "__main__":
    print("This module is ready.")
    print("Use prepare_and_save_recipes_for_ir(...) to create one final CSV for search.")