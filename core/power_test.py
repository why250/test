import time
from . import utils
from .test_context import TestContext

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
        fname = utils.save_power_results(results, final_status, site_id)
        if fname:
            context.log(f"Results saved to {fname}")
        else:
            context.log("Error saving results.")
