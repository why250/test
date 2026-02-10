import os
import csv
import yaml

class ConfigManager:
    def __init__(self):
        self.dac_config_path = "DAC_Config.csv"
        self.power_config_path = "Power_Config.yaml"

    def modify_dac_config(self, stage_index):
        """
        Modifies DAC_Config.csv.
        Sets DAC 1 to DAC i to -4.5V. Others to -2.5V.
        Stage 1: DAC1=-4.5V
        Stage 2: DAC1, DAC2=-4.5V
        ...
        """
        if not os.path.exists(self.dac_config_path):
            print(f"Warning: {self.dac_config_path} not found.")
            return

        rows = []
        with open(self.dac_config_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                ch_name = row['Channel']
                # Check if channel is DAC1..DAC32 (format DACx)
                if ch_name.startswith('DAC'):
                    try:
                        idx = int(ch_name.replace('DAC', ''))
                        # Logic: DAC 1 to i = -4.5V
                        # Note: SRS says "DAC 1...i". Assuming 1-based index for logic, but file might be 0-based or 1-based.
                        # Looking at previous DAC_Config.csv, it has DAC0, DAC1...
                        # SRS v3.0 Table: Stage 1 -> DAC1.
                        # Let's assume we modify DAC1, DAC2... based on stage.
                        if 1 <= idx <= 7:
                            if idx <= stage_index:
                                row['Voltage'] = '-4.5'
                            else:
                                row['Voltage'] = '-2.5'
                    except ValueError:
                        pass
                rows.append(row)
        
        with open(self.dac_config_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Updated {self.dac_config_path} for Stage {stage_index}")

    def modify_power_config(self, stage_index):
        """
        Modifies Power_Config.yaml.
        Sets DP1 CH2 Voltage.
        Reference: 1.6 + (0.3 * i)
        Stage 1: 1.9V
        Stage 2: 2.2V
        ...
        """
        if not os.path.exists(self.power_config_path):
            print(f"Warning: {self.power_config_path} not found.")
            return

        with open(self.power_config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or []
            
        # Formula from SRS v3.0: 1.6 + (0.3 * i)
        # Stage 1 (i=1) -> 1.9V
        # Stage 7 (i=7) -> 3.7V
        target_v = 1.6 + (0.3 * stage_index)
        
        updated = False
        for item in data:
            if item.get('instrument') == 'DP1' and int(item.get('channel')) == 2:
                item['voltage'] = round(target_v, 2)
                updated = True
                
        if not updated:
            print("Warning: DP1 CH2 not found in Power config.")
            
        with open(self.power_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, sort_keys=False)
        print(f"Updated {self.power_config_path}: DP1 CH2 -> {target_v:.2f}V")

    def get_power_limits(self):
        """
        Reads Power_limit_config.yaml and returns the list of limits.
        """
        limit_path = "Power_limit_config.yaml"
        if not os.path.exists(limit_path):
            print(f"Warning: {limit_path} not found.")
            return []
            
        with open(limit_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or []
