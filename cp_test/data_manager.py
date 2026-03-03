import csv
import os
from datetime import datetime

class DataManager:
    def __init__(self, result_file="Wafer_Sort_Results.csv"):
        self.result_file = result_file
        self.fieldnames = [
            'Test_Time', 'Site_ID', 'Row', 'Col', 
            'Final_Result', 'Fail_Reason', 
            'Power_Current', 'Power_Check_Result'
        ]
        
        # Add Stage columns
        for i in range(1, 8):
            prefix = f'S{i}'
            self.fieldnames.extend([
                f'{prefix}_DP_Current', # New field for DP current
                f'{prefix}_Input_Amp',
                f'{prefix}_Gain',
                f'{prefix}_Offset',
                f'{prefix}_No_Linearity',
                f'{prefix}_Max_INL', 
                f'{prefix}_Max_DNL', 
                f'{prefix}_Result'
            ])
        
        self._init_file()

    def _init_file(self):
        # Check if file exists. If so, read header to see if it matches current fieldnames.
        if os.path.exists(self.result_file):
            try:
                with open(self.result_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header != self.fieldnames:
                        print(f"Warning: {self.result_file} header mismatch. Renaming old file.")
                        f.close()
                        os.rename(self.result_file, f"{self.result_file}.bak_{datetime.now().strftime('%Y%m%d%H%M%S')}")
                        # Re-create below
                    else:
                        return # Header matches, all good
            except Exception:
                pass # Proceed to create new file

        with open(self.result_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()

    def save_result(self, data):
        """
        data is a dictionary matching fieldnames.
        """
        # Ensure timestamp if not present
        if 'Test_Time' not in data:
            data['Test_Time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        # Filter data to only include keys in fieldnames to avoid DictWriter error
        row_data = {k: v for k, v in data.items() if k in self.fieldnames}
        
        with open(self.result_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerow(row_data)
        print(f"Result saved for Site {data.get('Site_ID')}")
