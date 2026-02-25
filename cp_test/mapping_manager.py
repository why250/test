import csv
import os
import json

class MappingManager:
    def __init__(self, layout_file="wafer_layout.csv", json_file="wafer_layout.json"):
        self.layout_file = layout_file
        self.json_file = json_file
        self.mapping = {} # Site_ID -> (Row, Col)
        self.current_site_id = 1
        
        # Check and update from JSON if available
        self.update_layout_from_json()
        
        self.load_mapping()

    def update_layout_from_json(self):
        if not os.path.exists(self.json_file):
            return

        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return

        grid = config.get("layout_grid", [])
        start_id = config.get("start_site_id", 1)
        
        if not grid:
            return

        rows = []
        site_id = start_id
        
        for r_idx, row_data in enumerate(grid):
            current_row = r_idx + 1
            for c_idx, val in enumerate(row_data):
                current_col = c_idx + 1
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
            with open(self.layout_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
            print(f"Successfully generated {self.layout_file} from {self.json_file}")
        except Exception as e:
            print(f"Error writing CSV: {e}")

    def load_mapping(self):
        if not os.path.exists(self.layout_file):
            print(f"Warning: {self.layout_file} not found.")
            return

        with open(self.layout_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    site_id = int(row['Site_ID'])
                    r = int(row['Row'])
                    c = int(row['Col'])
                    self.mapping[site_id] = (r, c)
                except ValueError:
                    continue
        print(f"Loaded {len(self.mapping)} sites from {self.layout_file}")

    def get_coordinates(self, site_id):
        return self.mapping.get(site_id)

    def get_next_site_id(self):
        # Find the next valid site ID in the map
        next_id = self.current_site_id + 1
        if next_id in self.mapping:
            return next_id
        return None

    def set_current_site(self, site_id):
        if site_id in self.mapping:
            self.current_site_id = site_id
            return True
        return False
