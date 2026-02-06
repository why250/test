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

    def run_power_sequence(self, context: TestContext, mode="ON", config_file="Power_on_config.txt", limit_file="Power_limit_config.txt"):
        context.log(f"Starting Power {mode} Sequence...")
        
        # 1. Read Configurations
        configs = utils.parse_config_file(config_file)
        if not configs:
            context.log(f"Error: Could not read {config_file}")
            return False

        if mode == "OFF":
            configs = list(reversed(configs))

        limits = []
        if mode == "ON":
            limits = utils.parse_config_file(limit_file)

        results = []
        
        # 2. Execute Sequence
        for item in configs:
            if context.check_stop():
                context.log("Sequence stopped by user.")
                break
            
            # Format: (DPName, Channel, Voltage, Current)
            if len(item) < 4:
                context.log(f"Skipping invalid config: {item}")
                continue
                
            dp_name, ch, volt, curr = item[0], item[1], float(item[2]), float(item[3])
            
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
                
                meas_curr = dp.measure_current(ch)
                
                # Check limits
                status = self._check_limit(dp_name, ch, meas_curr, limits)
                
                msg = f"CH{ch} Current: {meas_curr:.4f}A ({status})"
                context.log(msg)
                results.append(f"{dp_name}, {ch}, {meas_curr:.4f}, {status}")
                
            else: # OFF
                dp.output_off(ch)
                context.log(f"CH{ch} OFF")
                time.sleep(0.5)

        # 3. Save Results (only for ON)
        if mode == "ON":
            self._save_results(results, context)
            
        return True

    def _check_limit(self, dp_name, ch, measured_val, limits):
        for lim in limits:
            # Limit Format: (DPName, Channel, Min, Max)
            if len(lim) >= 4 and lim[0] == dp_name and lim[1] == ch:
                min_c, max_c = float(lim[2]), float(lim[3])
                if min_c <= measured_val <= max_c:
                    return "PASS"
                else:
                    return "FAIL"
        return "NO_LIMIT"

    def _save_results(self, results, context):
        fname = f"Power_on_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(fname, 'w') as f:
                f.write("DP Name, Channel, Measured Current, Status\n")
                for r in results:
                    f.write(r + "\n")
            context.log(f"Results saved to {fname}")
        except Exception as e:
            context.log(f"Error saving results: {e}")

class LinearityTestLogic:
    """
    Encapsulates the logic for DC Linearity Testing.
    """
    def __init__(self, instrument_manager):
        self.inst_mgr = instrument_manager

    def run_test(self, context: TestContext, source_type, start_v, end_v, step_v, dac_alias, dac_ch, dm_alias, dg_alias):
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
            # dm.close() # Don't close shared instruments? Or yes? 
            # In a manager context, usually we keep them open. 
            # But previous logic closed them. Let's keep them open for efficiency or close if needed.
            # For now, let's NOT close them automatically to allow reuse in GUI.
            return None

        # 2. Generate Test Points
        try:
            steps = np.arange(start_v, end_v + step_v/1000.0, step_v)
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
            self._set_source_value(source_inst, source_type, dac_ch, v)
            
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
            self._save_results(input_vals, measured_vals, metrics, context)
            
        return input_vals, measured_vals, metrics

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

    def _set_source_value(self, inst, source_type, channel, voltage):
        if source_type == "DAC":
            # Assuming 10V range for calculation as per previous logic
            code = utils.calculate_dac_code("10", voltage)
            inst.set_output(channel, code)
        else:
            inst.set_dc_voltage(voltage)

    def _save_results(self, input_vals, measured_vals, metrics, context):
        fname = f"results/dc_linearity_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        os.makedirs("results", exist_ok=True)
        try:
            utils.save_linearity_results(fname, input_vals, measured_vals, metrics)
            context.log(f"Results saved to {fname}")
        except Exception as e:
            context.log(f"Error saving results: {e}")
