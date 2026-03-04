import time
import os
from datetime import datetime
import numpy as np
from . import utils

class TestContext:
    """
    Helper class to handle callbacks for logging and progress updates.
    Allows logic to be used with or without GUI.
    """
    def __init__(self, log_callback=None, progress_callback=None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.should_stop = False

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[LOG] {message}")

    def report_progress(self, value):
        if self.progress_callback:
            self.progress_callback(value)

    def check_stop(self):
        return self.should_stop

    def request_stop(self):
        self.should_stop = True

class PowerTestLogic:
    """
    Encapsulates the logic for Power ON/OFF sequences.
    """
    def __init__(self, instrument_manager):
        self.inst_mgr = instrument_manager

    def run_power_sequence(self, context: TestContext, mode="ON", config_file="config/Power_on_config.yaml", limit_file="config/Power_limit_config.yaml", site_id=None):
        context.log(f"Starting Power {mode} Sequence...")
        
        # 1. Read Configurations
        configs = utils.load_yaml_config(config_file)
        if not configs:
            context.log(f"Error: Could not read {config_file}")
            return False

        limits = utils.load_yaml_config(limit_file)
        
        # Validation: Check if DP channel quantity matches between config and limits
        if mode == "ON" and limits:
            config_channels = set()
            for item in configs:
                if 'instrument' in item and 'channel' in item:
                    config_channels.add((item['instrument'], item['channel']))
            
            limit_channels = set()
            for item in limits:
                if 'instrument' in item and 'channel' in item:
                    limit_channels.add((item['instrument'], item['channel']))
            
            if len(config_channels) != len(limit_channels):
                context.log(f"Warning: Inconsistent DP Channel quantity! Config: {len(config_channels)}, Limits: {len(limit_channels)}")
                # We just warn, not abort, as per requirement "give a hint"
            
            # Check for missing limits
            missing_limits = config_channels - limit_channels
            if missing_limits:
                context.log(f"Warning: Missing limits for channels: {missing_limits}")

        if mode == "OFF":
            configs = list(reversed(configs))

        results = [] # List of lists (steps -> measurements)
        active_channels = [] # List of tuples: (dp_name, ch, dp_obj)
        final_status = "PASS"
        
        # 2. Execute Sequence
        for item in configs:
            if context.check_stop():
                context.log("Sequence stopped by user.")
                break
            
            try:
                dp_name = item['instrument']
                ch = item['channel']
                volt = float(item['voltage'])
                curr = float(item['current'])
            except KeyError as e:
                context.log(f"Skipping invalid config item {item}: Missing key {e}")
                continue
                
            # Find instrument by Alias (DPName)
            dp = self.inst_mgr.get_instrument(dp_name)
            if not dp:
                context.log(f"Error: Instrument '{dp_name}' not found in registry.")
                continue
            
            if not dp.connected:
                if not dp.connect():
                    context.log(f"Error: Failed to connect to '{dp_name}'")
                    continue
            
            context.log(f"Processing {dp_name} CH{ch}: Set {volt}V, {curr}A")
            
            if mode == "ON":
                dp.set_channel(ch, volt, curr)
                dp.output_on(ch)
                time.sleep(1) # Wait for stability
                
                # Add to active channels if not present
                if not any(ac[0] == dp_name and ac[1] == ch for ac in active_channels):
                    active_channels.append((dp_name, ch, dp))
                
                # Measure all active channels
                step_measurements = []
                step_log_parts = []
                
                for ac_name, ac_ch, ac_dp in active_channels:
                    meas_curr = ac_dp.measure_current(ac_ch)
                    step_measurements.append({
                        'instrument': ac_name,
                        'channel': ac_ch,
                        'current': meas_curr
                    })
                    step_log_parts.append(f"{ac_name}.CH{ac_ch}={meas_curr:.4f}A")
                
                context.log(f"Step Measurements: {', '.join(step_log_parts)}")
                results.append(step_measurements)
                
            else: # OFF
                dp.output_off(ch)
                context.log(f"CH{ch} OFF")
                time.sleep(0.5)

        # 3. Save Results (only for ON)
        if mode == "ON":
            # Check limits on the LAST step measurements (all channels ON)
            if results:
                last_step = results[-1]
                for m in last_step:
                    status = self._check_limit(m['instrument'], m['channel'], m['current'], limits)
                    m['status'] = status
                    if status == "FAIL":
                        final_status = "FAIL"
            
            self._save_results(results, final_status, context, site_id)
            
        return True

    def _check_limit(self, dp_name, ch, measured_val, limits):
        for lim in limits:
            # Limit Format: Dict
            if lim.get('instrument') == dp_name and lim.get('channel') == ch:
                min_c = float(lim.get('min_current', -float('inf')))
                max_c = float(lim.get('max_current', float('inf')))
                if min_c <= measured_val <= max_c:
                    return "PASS"
                else:
                    return "FAIL"
        return "NO_LIMIT"

    def _save_results(self, results, final_status, context, site_id=None):
        folder = "results/power_on_result"
        if site_id is not None:
            folder = f"{folder}/{site_id}"
            
        os.makedirs(folder, exist_ok=True)
        fname = f"{folder}/Power_on_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(fname, 'w') as f:
                f.write(f"Power Sequence Result - Final Status: {final_status}\n")
                f.write("="*50 + "\n")
                
                for i, step_data in enumerate(results):
                    f.write(f"Step {i+1}:\n")
                    for m in step_data:
                        status_str = f" ({m['status']})" if 'status' in m else ""
                        f.write(f"  {m['instrument']} CH{m['channel']}: {m['current']:.4f}A{status_str}\n")
                    f.write("-" * 20 + "\n")
            context.log(f"Results saved to {fname}")
        except Exception as e:
            context.log(f"Error saving results: {e}")

class LinearityTestLogic:
    """
    Encapsulates the logic for DC Linearity Testing.
    """
    def __init__(self, instrument_manager):
        self.inst_mgr = instrument_manager

    def run_test(self, context: TestContext, source_type, start_v, step_v, points, dac_alias, dac_ch, dm_alias, dg_alias, site_id=None):
        context.log("Starting Linearity Test...")
        
        # 1. Connect Instruments (Lookup by Alias)
        if not dm_alias:
             context.log("Error: Multimeter alias not provided.")
             return None
             
        dm = self.inst_mgr.get_instrument(dm_alias)
        if not dm:
            context.log(f"Error: Multimeter '{dm_alias}' not found.")
            return None
        
        if not dm.connected:
            if not dm.connect():
                context.log(f"Failed to connect to Multimeter '{dm_alias}'.")
                return None

        source_inst = self._connect_source(source_type, dac_alias, dg_alias, context)
        if not source_inst:
            return None

        # Determine DAC Range if needed
        dac_range = 10.0
        if source_type == "DAC":
             dac_range = self._get_dac_range(dac_ch)
             context.log(f"Using DAC Range: {dac_range}V for CH{dac_ch}")

        # Initialize DG if selected
        if source_type == "DG":
            # Assuming channel 1 for now or we could add a DG Channel field
            # The reference script uses CH1.
            dg_ch = 1 
            if hasattr(source_inst, 'initialize_dc_mode'):
                 context.log(f"Initializing {dg_alias} to DC mode...")
                 source_inst.initialize_dc_mode(dg_ch)
                 time.sleep(1)

        # 2. Generate Test Points
        try:
            # steps = np.arange(start_v, end_v + step_v/1000.0, step_v)
            steps = start_v + np.arange(points) * step_v
        except Exception as e:
            context.log(f"Error generating steps: {e}")
            return None
        
        input_vals = []
        measured_vals = []
        total_steps = len(steps)
        
        # 3. Execution Loop
        for idx, v in enumerate(steps):
            if context.check_stop():
                context.log("Test stopped by user.")
                break
            
            # Set Source
            self._set_source_value(source_inst, source_type, dac_ch, v, dac_range)
            
            time.sleep(0.2) # Settle time
            
            # Measure
            meas = dm.measure_voltage()
            
            input_vals.append(v)
            measured_vals.append(meas)
            
            context.log(f"Set: {v:.4f}V, Meas: {meas:.4f}V")
            context.report_progress(int((idx + 1) / total_steps * 100))

        # 5. Analysis & Save
        metrics = None
        if len(input_vals) > 1:
            metrics = utils.calculate_linearity_metrics(input_vals, measured_vals)
            self._save_results(input_vals, measured_vals, metrics, context, site_id)
            
        return input_vals, measured_vals, metrics

    def _get_dac_range(self, channel_idx, config_file="config/DAC_Config.csv"):
        configs = utils.load_csv_config(config_file)
        if not configs:
            return 10.0 # Default fallback
            
        target_idx = -1
        try:
            target_idx = int(channel_idx)
        except ValueError:
            return 10.0

        for item in configs:
            try:
                ch_name = item['Channel']
                if ch_name.startswith("DAC"):
                    idx = int(ch_name.replace("DAC", ""))
                    if idx == target_idx:
                        return float(item['Range'])
            except:
                continue
        return 10.0 # Default if not found

    def _connect_source(self, source_type, dac_alias, dg_alias, context):
        alias = dac_alias if source_type == "DAC" else dg_alias
        
        if not alias:
            context.log(f"Error: Source alias not provided.")
            return None

        inst = self.inst_mgr.get_instrument(alias)
        if not inst:
            context.log(f"Error: Source '{alias}' not found.")
            return None
            
        if not inst.connected:
            if not inst.connect():
                context.log(f"Failed to connect to Source '{alias}'.")
                return None
        return inst

    def _set_source_value(self, inst, source_type, channel, voltage, dac_range=10.0):
        if source_type == "DAC":
            # Use the determined range for calculation
            code = utils.calculate_dac_code(str(dac_range), voltage)
            inst.set_output(channel, code)
        else:
            # DG
            # channel argument here comes from dac_ch which might not be relevant for DG if we assume CH1
            # But let's pass 1 for DG
            inst.set_dc_voltage(voltage, channel=1)

    def _save_results(self, input_vals, measured_vals, metrics, context, site_id=None):
        folder = "results/dc_linearity_result"
        if site_id is not None:
            folder = f"{folder}/{site_id}"
            
        os.makedirs(folder, exist_ok=True)
        fname = f"{folder}/dc_linearity_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            utils.save_linearity_results(fname, input_vals, measured_vals, metrics)
            context.log(f"Results saved to {fname}")
        except Exception as e:
            context.log(f"Error saving results: {e}")
