import os
import csv
import yaml
import shutil
import io

class ConfigManager:
    def __init__(self):
        self.dac_config_path = "config/DAC_Config.csv"
        self.power_config_path = "config/Power_Config.yaml"
        self.cp_test_config_path = "config/cp_test_config.yaml"
        self.cp_hardware_config_path = "config/cp_hardware_config.yaml"
        
        # Init paths
        self.dac_init_path = "config/DAC_Config_Init.csv"
        self.power_init_path = "config/Power_Config_Init.yaml"

    def _read_file_with_fallback(self, path):
        """
        Helper to read file content with multiple encoding attempts.
        """
        if not os.path.exists(path):
            return None
            
        encodings = ['utf-8-sig', 'utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'gbk', 'gb18030', 'cp1252', 'latin-1']
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        
        # If all fail, try opening with errors='replace' as a last resort
        print(f"Warning: Could not decode {path} with standard encodings. using utf-8 with replace.")
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    def _read_csv_robust(self, path):
        """
        Reads CSV data. Refers to cp_test/mapping_manager.py style but with encoding support.
        """
        if not os.path.exists(path):
            return [], None

        # Check for TSD encryption header first
        try:
            with open(path, 'rb') as f:
                header = f.read(20)
                if b'%TSD-Header' in header:
                    print(f"CRITICAL ERROR: File {path} is encrypted by Titus Security (TSD).")
                    print("The packaged application cannot decrypt this file.")
                    print("Please save the file as PLAIN TEXT (remove protection) or decrypt it manually.")
                    return [], None
        except:
            pass

        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb18030', 'cp1252']
        
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    # Read all content first to handle potential read errors eagerly
                    content = f.read()
                    
                    # Normalize newlines
                    content = content.replace('\r\n', '\n').replace('\r', '\n')
                    
                    f_io = io.StringIO(content)
                    reader = csv.DictReader(f_io)
                    
                    if reader.fieldnames:
                        # Clean fieldnames
                        fieldnames = [str(name).strip().lstrip('\ufeff') for name in reader.fieldnames]
                        
                        # Verify it looks like our config
                        if 'Channel' in fieldnames:
                            rows = []
                            for row in reader:
                                clean_row = {k.strip(): v for k, v in row.items() if k}
                                if 'Channel' in clean_row:
                                    rows.append(clean_row)
                            return rows, fieldnames
            except UnicodeDecodeError:
                continue
            except Exception as e:
                # print(f"Error parsing with {enc}: {e}")
                continue
        
        print(f"Warning: Could not read {path} with standard encodings or 'Channel' header missing.")
        return [], None

    def get_cp_test_config(self):
        """
        Reads config/cp_test_config.yaml and returns the configuration dict.
        """
        content = self._read_file_with_fallback(self.cp_test_config_path)
        if content is None:
            print(f"Warning: {self.cp_test_config_path} not found.")
            return {}
            
        return yaml.safe_load(content) or {}

    def get_cp_hardware_config(self):
        """
        Reads config/cp_hardware_config.yaml
        """
        content = self._read_file_with_fallback(self.cp_hardware_config_path)
        if content is None:
            return {}
        return yaml.safe_load(content) or {}

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
        
        rows, fieldnames = self._read_csv_robust(self.dac_config_path)
        
        if not rows:
            print(f"Warning: Could not read {self.dac_config_path} or file is empty.")
            return

        if not fieldnames:
            fieldnames = ['Channel', 'Range', 'Voltage'] # Default fallback

        # Apply updates
        for row in rows:
            ch_name = row.get('Channel')
            if not ch_name: continue
            
            for dac_alias, channels in dac_updates.items():
                if channels:
                    for ch_idx, voltage in channels.items():
                        target_ch_name = f"DAC{ch_idx}"
                        if ch_name == target_ch_name:
                            row['Voltage'] = str(voltage)
        
        # Write back cleanly as UTF-8
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
        
        content = self._read_file_with_fallback(self.power_config_path)
        if content is None:
            print(f"Warning: {self.power_config_path} not found.")
            return

        data = yaml.safe_load(content) or []
            
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
        init_rows, _ = self._read_csv_robust(self.dac_init_path)
        
        for row in init_rows:
            if 'Channel' in row and 'Voltage' in row:
                init_values[row['Channel']] = row['Voltage']
        
        # Update current config
        rows, fieldnames = self._read_csv_robust(self.dac_config_path)
        
        if not rows:
            return

        if not fieldnames:
             fieldnames = ['Channel', 'Range', 'Voltage']

        for row in rows:
            ch_name = row.get('Channel')
            if not ch_name: continue
            
            # Check if this channel was modified in this stage
            for dac_alias, channels in dac_updates.items():
                if channels:
                    for ch_idx, _ in channels.items():
                        target_ch_name = f"DAC{ch_idx}"
                        if ch_name == target_ch_name:
                            # Revert to initial value
                            if ch_name in init_values:
                                row['Voltage'] = init_values[ch_name]
        
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
        content = self._read_file_with_fallback(limit_path)
        if content is None:
            print(f"Warning: {limit_path} not found.")
            return []
            
        return yaml.safe_load(content) or []

    def get_stage_current_limits(self):
        """
        Reads config/cp_stage_current_config.yaml and returns the limits dict.
        """
        limit_path = "config/cp_stage_current_config.yaml"
        content = self._read_file_with_fallback(limit_path)
        if content is None:
            print(f"Warning: {limit_path} not found.")
            return {}
            
        return yaml.safe_load(content) or {}
