import json
import csv
import os

def generate_layout_csv(json_file="wafer_layout.json", csv_file="wafer_layout.csv"):
    if not os.path.exists(json_file):
        print(f"Error: {json_file} not found.")
        return

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return

    grid = config.get("layout_grid", [])
    start_id = config.get("start_site_id", 1)
    
    if not grid:
        print("Error: 'layout_grid' is empty or missing in JSON.")
        return

    rows = []
    site_id = start_id
    
    # Iterate through the grid
    # row_idx is 0-based index from JSON, mapped to 1-based Row in CSV
    # col_idx is 0-based index from JSON, mapped to 1-based Col in CSV
    for r_idx, row_data in enumerate(grid):
        current_row = r_idx + 1
        for c_idx, val in enumerate(row_data):
            current_col = c_idx + 1
            
            # If val is 1 (or true), it's a valid site
            if val:
                rows.append({
                    "Site_ID": site_id,
                    "Row": current_row,
                    "Col": current_col
                })
                site_id += 1

    # Write to CSV
    headers = ["Site_ID", "Row", "Col"]
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Successfully generated {csv_file} with {len(rows)} sites.")
    except Exception as e:
        print(f"Error writing CSV: {e}")

if __name__ == "__main__":
    generate_layout_csv()
