import json

# --- Load both JSON files ---
with open("previous_orders_2025-11-07_23-41-18.json", "r", encoding="utf-8") as f1:
    data1 = json.load(f1)

with open("woocommerce.json", "r", encoding="utf-8") as f2:
    data2 = json.load(f2)

# --- Extract IDs from both ---
ids1 = {item["id"] for item in data1}
ids2 = {item["id"] for item in data2}

# --- Compare ---
missing_in_file2 = ids1 - ids2  # IDs present in file1 but not in file2
missing_in_file1 = ids2 - ids1  # IDs present in file2 but not in file1

# --- Prepare results ---
results = {
    "total_in_file1": len(ids1),
    "total_in_file2": len(ids2),
    "missing_in_file2": sorted(list(missing_in_file2)),
    "missing_in_file1": sorted(list(missing_in_file1))
}

# --- Save results to file ---
with open("comparison_results.json", "w", encoding="utf-8") as outfile:
    json.dump(results, outfile, indent=4)

# --- Print summary ---
print(f"✅ Comparison complete! Results saved to comparison_results.json\n")
print(f"Total in file1: {len(ids1)} | file2: {len(ids2)}")
print(f"Missing in file2: {len(missing_in_file2)}")
print(f"Missing in file1: {len(missing_in_file1)}")
