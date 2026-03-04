import csv
import os
from datetime import datetime
from automation.config_manager import ConfigManager

class DataManager:
    def __init__(self, result_file="Wafer_Sort_Results.csv", max_stages=7):
        self.result_file = result_file
        self.max_stages = max_stages
        self.config_manager = ConfigManager()
        self.fieldnames = [
            'Test_Time', 'Site_ID', 'Row', 'Col', 
            'Final_Result', 'Fail_Reason', 
            'Power_Check_Result'
        ]
        
        # Load Hardware Config for dynamic column names
        hw_config = self.config_manager.get_cp_hardware_config()
        
        # Add Stage columns
        for i in range(1, self.max_stages + 1):
            prefix = f'S{i}'
            
            # Determine DP Current column name
            dp_col_name = f'{prefix}_DP_Current' # Default
            
            stage_cfg = hw_config.get('stages', {}).get(i, {})
            power_updates = stage_cfg.get('power', {})
            
            if power_updates:
                for dp_name, channels in power_updates.items():
                    if channels:
                        for ch, _ in channels.items():
                            # Format: S{i}_{Instrument}_CH{Channel}
                            # Example: S1_DP1_CH2
                            dp_col_name = f'{prefix}_{dp_name}_CH{ch}'
                            break 
                    break

            self.fieldnames.extend([
                dp_col_name, 
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
        
        try:
            with open(self.result_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(row_data)
            print(f"Result saved for Site {data.get('Site_ID')}")
            return True
        except PermissionError:
            print(f"Error: Could not write to {self.result_file}. Please close the file if it is open.")
            return False
        except Exception as e:
            print(f"Error saving result: {e}")
            return False
