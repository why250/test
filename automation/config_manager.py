import os
import csv
import yaml
import shutil

class ConfigManager:
    def __init__(self):
        self.dac_config_path = "config/DAC_Config.csv"
        self.power_config_path = "config/Power_Config.yaml"
        self.cp_test_config_path = "config/cp_test_config.yaml"
        self.cp_hardware_config_path = "config/cp_hardware_config.yaml"
        
        # Init paths
        self.dac_init_path = "config/DAC_Config_Init.csv"
        self.power_init_path = "config/Power_Config_Init.yaml"

    def get_cp_test_config(self):
        """
        Reads config/cp_test_config.yaml and returns the configuration dict.
        """
        if not os.path.exists(self.cp_test_config_path):
            print(f"Warning: {self.cp_test_config_path} not found.")
            return {}
            
        with open(self.cp_test_config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def get_cp_hardware_config(self):
        """
        Reads config/cp_hardware_config.yaml
        """
        if not os.path.exists(self.cp_hardware_config_path):
            return {}
        with open(self.cp_hardware_config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def reset_to_initial_config(self):
        """
        Resets DAC and Power configs to their initial state.
        """
        try:
            if os.path.exists(self.dac_init_path):
                shutil.copy(self.dac_init_path, self.dac_config_path)
                print(f"Reset {self.dac_config_path} from {self.dac_init_path}")
            else:
                print(f"Warning: {self.dac_init_path} not found. Cannot reset.")

            if os.path.exists(self.power_init_path):
                shutil.copy(self.power_init_path, self.power_config_path)
                print(f"Reset {self.power_config_path} from {self.power_init_path}")
            else:
                print(f"Warning: {self.power_init_path} not found. Cannot reset.")
        except Exception as e:
            print(f"Error resetting configs: {e}")

    def modify_dac_config(self, stage_index):
        """
        Modifies config/DAC_Config.csv based on config/cp_hardware_config.yaml
        """
        hw_config = self.get_cp_hardware_config()
        stage_cfg = hw_config.get('stages', {}).get(stage_index, {})
        dac_updates = stage_cfg.get('dac', {}) # e.g. {'DAC1': {1: -4.5}}
        
        if not os.path.exists(self.dac_config_path):
            print(f"Warning: {self.dac_config_path} not found.")
            return

        # If no updates for this stage, we might still want to proceed or just return.
        # But if we rely on this function, let's proceed.
        
        rows = []
        with open(self.dac_config_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                ch_name = row['Channel']
                
                # Apply updates
                for dac_alias, channels in dac_updates.items():
                    if channels:
                        for ch_idx, voltage in channels.items():
                            target_ch_name = f"DAC{ch_idx}"
                            if ch_name == target_ch_name:
                                row['Voltage'] = str(voltage)
                                
                rows.append(row)
        
        with open(self.dac_config_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Updated {self.dac_config_path} for Stage {stage_index}")

    def modify_power_config(self, stage_index):
        """
        Modifies config/Power_Config.yaml based on config/cp_hardware_config.yaml
        """
        hw_config = self.get_cp_hardware_config()
        stage_cfg = hw_config.get('stages', {}).get(stage_index, {})
        power_updates = stage_cfg.get('power', {}) # e.g. {'DP1': {2: 1.6}}
        
        if not os.path.exists(self.power_config_path):
            print(f"Warning: {self.power_config_path} not found.")
            return

        with open(self.power_config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or []
            
        updated = False
        for item in data:
            inst = item.get('instrument')
            ch = item.get('channel')
            
            if inst in power_updates:
                ch_updates = power_updates[inst]
                if ch in ch_updates:
                    item['voltage'] = ch_updates[ch]
                    updated = True
        
        with open(self.power_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, sort_keys=False)
        print(f"Updated {self.power_config_path} for Stage {stage_index}")

    def revert_dac_changes(self, stage_index):
        """
        Reverts DAC changes made in stage_index to their initial values (from DAC_Config_Init.csv).
        """
        hw_config = self.get_cp_hardware_config()
        stage_cfg = hw_config.get('stages', {}).get(stage_index, {})
        dac_updates = stage_cfg.get('dac', {}) # e.g. {'DAC1': {1: -4.5}}
        
        if not dac_updates:
            return

        # Load Initial Config to get original values
        init_values = {}
        if os.path.exists(self.dac_init_path):
             with open(self.dac_init_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    init_values[row['Channel']] = row['Voltage']
        
        # Update current config
        if not os.path.exists(self.dac_config_path):
            return

        rows = []
        with open(self.dac_config_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                ch_name = row['Channel']
                
                # Check if this channel was modified in this stage
                for dac_alias, channels in dac_updates.items():
                    if channels:
                        for ch_idx, _ in channels.items():
                            target_ch_name = f"DAC{ch_idx}"
                            if ch_name == target_ch_name:
                                # Revert to initial value
                                if ch_name in init_values:
                                    row['Voltage'] = init_values[ch_name]
                                
                rows.append(row)
        
        with open(self.dac_config_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Reverted DAC changes for Stage {stage_index} in {self.dac_config_path}")

    def reset_power_to_initial(self):
        """
        Resets Power config to initial state.
        """
        if os.path.exists(self.power_init_path):
            shutil.copy(self.power_init_path, self.power_config_path)
            print(f"Reset {self.power_config_path} from {self.power_init_path}")

    def get_power_limits(self):
        """
        Reads config/Power_limit_config.yaml and returns the list of limits.
        """
        limit_path = "config/Power_limit_config.yaml"
        if not os.path.exists(limit_path):
            print(f"Warning: {limit_path} not found.")
            return []
            
        with open(limit_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or []
