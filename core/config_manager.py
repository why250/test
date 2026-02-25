import time
from . import utils

class ConfigManager:
    def __init__(self, instrument_manager, log_callback=None):
        self.inst_mgr = instrument_manager
        self.log_callback = log_callback

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[ConfigManager] {message}")

    def apply_dac_config(self, config_file, dac_alias):
        self.log("Applying DAC Configuration...")
        configs = utils.load_csv_config(config_file)
        if not configs:
            self.log(f"Error: {config_file} not found or empty.")
            return False
            
        dac = self.inst_mgr.get_instrument(dac_alias)
        
        if not dac:
            self.log(f"Error: DAC '{dac_alias}' not found in registry. Please add it in Device Manager.")
            return False
        
        if not dac.connected:
            if not dac.connect():
                self.log(f"Error: Could not connect to DAC '{dac_alias}'")
                return False
            
        # Pre-process configs into a dictionary
        dac_data = {} 
        for item in configs:
            try:
                ch_name = item['Channel']
                ch_idx = int(ch_name.replace("DAC", ""))
                dac_data[ch_idx] = {
                    'range': float(item['Range']),
                    'voltage': float(item['Voltage'])
                }
            except Exception:
                continue

        # Process in chunks of 4 channels (Total 32 channels: 0-31)
        for i in range(0, 32, 4):
            chunk_indices = [i, i+1, i+2, i+3]
            
            # Prepare data for this chunk
            chunk_ranges = []
            
            # Check if any channel in this chunk is present in the config file
            # If so, we process the whole chunk (filling missing ones with defaults)
            # If the whole chunk is missing from config, we skip it
            chunk_has_data = any(idx in dac_data for idx in chunk_indices)
            if not chunk_has_data:
                continue

            for idx in chunk_indices:
                if idx in dac_data:
                    chunk_ranges.append(dac_data[idx]['range'])
                else:
                    chunk_ranges.append(2.5) # Default range

            # 1. Calculate and Send Range/Gear Command
            # Logic from config_loader.py
            dac_chip_num = 0 if i < 16 else 1
            register_addr = 13 - (i % 16) // 4
            
            gear_code = utils.calculate_gear_code(chunk_ranges)
            
            cmd_range = f"DAC{dac_chip_num:02d} {register_addr} {gear_code};"
            self.log(f"Set Range Group {i}-{i+3}: {cmd_range}")
            dac.send_raw_command(cmd_range)
            time.sleep(0.1)
            
            # 2. Send Output Commands for channels in this chunk
            for j, idx in enumerate(chunk_indices):
                if idx in dac_data:
                    v_range = chunk_ranges[j]
                    target_v = dac_data[idx]['voltage']
                    
                    code = utils.calculate_dac_code(str(v_range), target_v)
                    self.log(f"Set DAC{idx} ({v_range}V) to {target_v}V -> Code {code}")
                    dac.set_output(idx, code)
                    time.sleep(0.05)
        
        self.log("DAC Configuration Completed.")
        return True

    def apply_power_config(self, config_file):
        self.log("Applying Power Configuration...")
        configs = utils.load_yaml_config(config_file)
        if not configs:
            self.log(f"Error: {config_file} not found.")
            return False
            
        for item in configs:
            try:
                dp_name = item['instrument']
                ch = item['channel']
                volt = float(item['voltage'])
                curr = float(item['current'])
                
                dp = self.inst_mgr.get_instrument(dp_name)
                if not dp:
                    self.log(f"Error: Power Supply '{dp_name}' not found in registry.")
                    continue
                    
                if not dp.connected:
                    dp.connect()
                
                self.log(f"Set {dp_name} CH{ch}: {volt}V, {curr}A")
                dp.set_channel(ch, volt, curr)
            except Exception as e:
                self.log(f"Error setting DP: {e}")
        
        self.log("Power Configuration Completed.")
        return True
