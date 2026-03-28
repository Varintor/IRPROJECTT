import pandas as pd
import os

# Check both CSV files
updated_file = "resources/recipes_updated.csv"
final_file = "resources/recipes_final_for_search.csv"

print("=" * 80)
print("📊 Comparing CSV Files")
print("=" * 80)

# Load recipes_updated.csv
print("\n🔍 Checking recipes_updated.csv...")
try:
    df_updated = pd.read_csv(updated_file, nrows=5)
    print(f"✅ Loaded successfully!")
    print(f"   Size: {os.path.getsize(updated_file) / (1024**3):.2f} GB")
    print(f"   Columns: {list(df_updated.columns)}")
    print(f"   Total columns: {len(df_updated.columns)}")
    print(f"\n   First row preview:")
    for col in df_updated.columns[:8]:
        print(f"   - {col}: {df_updated[col].iloc[0]}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 80)

# Load recipes_final_for_search.csv
print("\n🔍 Checking recipes_final_for_search.csv...")
try:
    df_final = pd.read_csv(final_file, nrows=5)
    print(f"✅ Loaded successfully!")
    print(f"   Size: {os.path.getsize(final_file) / (1024**3):.2f} GB")
    print(f"   Columns: {list(df_final.columns)}")
    print(f"   Total columns: {len(df_final.columns)}")
    print(f"\n   First row preview:")
    for col in df_final.columns[:8]:
        print(f"   - {col}: {df_final[col].iloc[0]}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 80)
print("\n📋 Column Comparison:")
print("=" * 80)

try:
    # Get all columns
    df_updated_full = pd.read_csv(updated_file, nrows=1)
    df_final_full = pd.read_csv(final_file, nrows=1)

    updated_cols = set(df_updated_full.columns)
    final_cols = set(df_final_full.columns)

    print(f"\n✅ Unique to recipes_updated.csv ({len(updated_cols - final_cols)} columns):")
    for col in sorted(updated_cols - final_cols):
        print(f"   + {col}")

    print(f"\n✅ Unique to recipes_final_for_search.csv ({len(final_cols - updated_cols)} columns):")
    for col in sorted(final_cols - updated_cols):
        print(f"   - {col}")

    print(f"\n✅ Common columns ({len(updated_cols & final_cols)} columns):")
    common_cols = sorted(updated_cols & final_cols)
    important_cols = ['recipe_id', 'name', 'category', 'processed_text', 'images', 'ingredient_parts', 'instructions']
    for col in important_cols:
        if col in common_cols:
            print(f"   ✓ {col}")

    # Check required columns for search
    required_cols = ['recipe_id', 'name', 'category', 'processed_text']
    print(f"\n🔍 Required columns for search:")
    for col in required_cols:
        in_updated = col in updated_cols
        in_final = col in final_cols
        updated_status = "✅" if in_updated else "❌"
        final_status = "✅" if in_final else "❌"
        print(f"   {updated_status} {final_status} {col}")

except Exception as e:
    print(f"❌ Error comparing: {e}")

print("\n" + "=" * 80)
print("\n💡 Recommendation:")
if 'recipe_id' in updated_cols and 'name' in updated_cols and 'processed_text' in updated_cols:
    print("✅ recipes_updated.csv has required columns - CAN BE USED!")
else:
    print("❌ recipes_updated.csv missing required columns")
