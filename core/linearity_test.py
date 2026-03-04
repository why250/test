import time
import os
from datetime import datetime
import numpy as np
from . import utils
from .test_context import TestContext

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
