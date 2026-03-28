import sys
import pandas as pd

# Set UTF-8 encoding for stdout
sys.stdout.reconfigure(encoding='utf-8')

try:
    print("Testing PKL load with pandas...")
    df = pd.read_pickle("../cleaned_ready_for_es.pkl")
    print(f"SUCCESS: Loaded {len(df)} recipes")
    print(f"Columns: {list(df.columns)[:5]}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
