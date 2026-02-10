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
        # Add Stage columns dynamically or fixed? SRS says Stage 1-7.
        for i in range(1, 8):
            prefix = f'S{i}'
            self.fieldnames.extend([
                f'{prefix}_Gain_Config', 
                f'{prefix}_Input_Amp', 
                f'{prefix}_Max_INL', 
                f'{prefix}_Max_DNL', 
                f'{prefix}_Result'
            ])
        
        self._init_file()

    def _init_file(self):
        if not os.path.exists(self.result_file):
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
            
        with open(self.result_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerow(data)
        print(f"Result saved for Site {data.get('Site_ID')}")
