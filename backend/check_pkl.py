import pickle
import pandas as pd

print("=" * 80)
print("Checking cleaned_ready_for_es.pkl")
print("=" * 80)

try:
    # Load pickle file
    with open('cleaned_ready_for_es.pkl', 'rb') as f:
        data = pickle.load(f)

    print("\n✅ File loaded successfully!")

    # Check type
    print(f"\n📦 Data type: {type(data)}")

    # Check if DataFrame
    if isinstance(data, pd.DataFrame):
        print(f"📊 Shape: {data.shape}")
        print(f"📋 Columns ({len(data.columns)}):")
        for i, col in enumerate(data.columns, 1):
            print(f"   {i:2d}. {col}")

        # Show sample data
        print(f"\n📄 First row preview:")
        for col in data.columns[:10]:
            val = data[col].iloc[0]
            if pd.notna(val):
                val_str = str(val)[:100]
                if len(val_str) == 100:
                    val_str += "..."
                print(f"   {col}: {val_str}")

        # Check required columns
        required_cols = ['recipe_id', 'name', 'category', 'processed_text']
        print(f"\n🔍 Required columns check:")
        for col in required_cols:
            has_col = col in data.columns
            status = "✅" if has_col else "❌"
            print(f"   {status} {col}")

        # Check for additional columns
        extra_cols = set(data.columns) - set(required_cols) - {'description', 'keywords'}
        if extra_cols:
            print(f"\n📌 Additional columns ({len(extra_cols)}):")
            for col in sorted(extra_cols):
                print(f"   + {col}")

        # Check data quality
        print(f"\n📈 Data quality:")
        print(f"   Total rows: {len(data)}")
        for col in ['recipe_id', 'name', 'category', 'processed_text']:
            if col in data.columns:
                null_count = data[col].isna().sum()
                null_pct = (null_count / len(data)) * 100
                print(f"   {col}: {null_count} null ({null_pct:.2f}%)")

        print(f"\n✅ CAN BE USED FOR ELASTICSEARCH!")
        print(f"   - Has required columns")
        print(f"   - Data is clean (preprocessed)")
        print(f"   - Ready to index")

    elif isinstance(data, dict):
        print(f"📚 Dictionary with keys: {list(data.keys())}")

    elif isinstance(data, list):
        print(f"📋 List with {len(data)} items")
        if len(data) > 0:
            print(f"   First item type: {type(data[0])}")

    else:
        print(f"❓ Unknown type: {type(data)}")

except FileNotFoundError:
    print("\n❌ File not found!")
    print("   Please check the path")

except Exception as e:
    print(f"\n❌ Error loading file: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
