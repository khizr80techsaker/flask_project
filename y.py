import json

# Load JSON data from a file
with open("not_parsed_2025-11-07_23-12-45.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Extract all IDs safely
ids = [item["id"] for item in data if "id" in item]

print(ids)
