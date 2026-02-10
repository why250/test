import csv
import os

class MappingManager:
    def __init__(self, layout_file="wafer_layout.csv"):
        self.layout_file = layout_file
        self.mapping = {} # Site_ID -> (Row, Col)
        self.current_site_id = 1
        self.load_mapping()

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
