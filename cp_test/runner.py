import time
from PySide6.QtCore import QObject, Signal, QTimer
from automation.test_sequencer import AutoTestSequencer
from automation.config_manager import ConfigManager
from .data_manager import DataManager

# Debug Constant: Abort test if Power Limit fails?
ABORT_ON_POWER_FAIL = False
# Debug Constant: Abort test if Linearity Limit fails?
ABORT_ON_NONLINEARITY_FAIL = False
# Debug Constant: Abort test if Stage Current Limit fails?
ABORT_ON_STAGE_CURRENT_FAIL = False
NO_LINEARITY_LIMIT = 1.0 # 1%

class CPTestRunner(QObject):
    finished = Signal(dict) # Emits result data
    log_message = Signal(str)

    def __init__(self, window, site_id, row, col):
        super().__init__()
        self.window = window
        self.site_id = site_id
        self.row = row
        self.col = col
        
        self.config_manager = ConfigManager()
        
        # Determine max_stages from config
        self.cp_config = self.config_manager.get_cp_test_config()
        self.max_stages = 7 # Default
        if self.cp_config and 'stages' in self.cp_config:
            try:
                stages = [int(k) for k in self.cp_config['stages'].keys()]
                if stages:
                    self.max_stages = max(stages)
            except:
                pass
                
        self.data_manager = DataManager(max_stages=self.max_stages)
        
        # Reusing logic from AutoTestSequencer where possible, 
        # but we need finer control for the "Fuse" mechanism.
        self.sequencer = AutoTestSequencer(window) 
        
        self.current_stage = 1
        # self.max_stages = 7 # Already set above
        self.test_data = {
            'Site_ID': site_id,
            'Row': row,
            'Col': col,
            'Final_Result': 'PENDING',
            'Fail_Reason': ''
        }
        self.is_running = False
        self.cp_config = {}

    def start(self):
        self.is_running = True
        self.log_message.emit(f"Starting CP Test for Site {self.site_id} (R{self.row}, C{self.col})")
        
        # Reset Configs to Initial State
        self.config_manager.reset_to_initial_config()
        self.log_message.emit("Reset DAC/Power configs to initial state.")

        # Load CP Test Config
        # self.cp_config is already loaded in __init__ but let's refresh it in case file changed
        self.cp_config = self.config_manager.get_cp_test_config()
        if not self.cp_config:
            self.log_message.emit("Warning: config/cp_test_config.yaml not found or empty. Using default settings.")
        else:
            self.log_message.emit("Loaded config/cp_test_config.yaml")
            # Update max_stages if changed
            if 'stages' in self.cp_config:
                try:
                    stages = [int(k) for k in self.cp_config['stages'].keys()]
                    if stages:
                        self.max_stages = max(stages)
                except:
                    pass

        # 1. Power On
        self.log_message.emit("Executing Power On Sequence...")
        self.window.start_power_on(site_id=self.site_id)
        
        # Hook into power worker
        if hasattr(self.window, 'pwr_worker') and self.window.pwr_worker:
            self.window.pwr_worker.finished_signal.connect(self.on_power_on_finished)
        else:
            # Fallback
            QTimer.singleShot(500, self._attach_power_on_signal)

    def _attach_power_on_signal(self):
        if hasattr(self.window, 'pwr_worker') and self.window.pwr_worker:
            self.window.pwr_worker.finished_signal.connect(self.on_power_on_finished)
        else:
            self.log_message.emit("Error: Could not attach to Power Worker.")
            self.abort_test("System Error")

    def on_power_on_finished(self):
        try:
            self.window.pwr_worker.finished_signal.disconnect(self.on_power_on_finished)
        except:
            pass
            
        if not self.is_running: return

        # 2. Power Check (Critical Fuse)
        self.log_message.emit("Checking Power Limits...")
        power_status, current_val = self.check_power_limits()
        
        self.test_data['Power_Check_Result'] = power_status
        
        if power_status == "FAIL":
            self.test_data['Final_Result'] = 'FAIL'
            if ABORT_ON_POWER_FAIL:
                self.log_message.emit("CRITICAL: Power Limit Exceeded! Aborting Test.")
                self.test_data['Fail_Reason'] = 'Power_Limit'
                self.finish_test() # Go directly to Power Off
                return
            else:
                self.log_message.emit("WARNING: Power Limit Exceeded! Continuing Test (Debug Mode).")
                # self.test_data['Power_Check_Result'] = 'FAIL (Ignored)' # Removed per request to keep it as FAIL or PASS correctly
        
        # 3. Start Linearity Stages
        self.run_stage()

    def check_power_limits(self):
        # Similar to AutoTestSequencer but returns status
        limits = self.config_manager.get_power_limits()
        if not limits:
            return "PASS", 0.0 # No limits defined

        max_current_measured = 0.0
        overall_status = "PASS"

        for limit in limits:
            inst_name = limit.get('instrument')
            try:
                channel = int(limit.get('channel'))
                min_c = float(limit.get('min_current', -float('inf')))
                max_c = float(limit.get('max_current', float('inf')))
            except:
                continue

            inst = self.window.inst_mgr.get_instrument(inst_name)
            if inst and inst.connected:
                try:
                    meas = inst.measure_current(channel)
                    if meas > max_current_measured:
                        max_current_measured = meas
                    
                    if not (min_c <= meas <= max_c):
                        overall_status = "FAIL"
                        self.log_message.emit(f"FAIL: {inst_name} CH{channel} Current {meas:.4f}A out of range ({min_c}, {max_c})")
                except Exception as e:
                    self.log_message.emit(f"Error measuring {inst_name}: {e}")
                    overall_status = "FAIL"
        
        return overall_status, max_current_measured

    def run_stage(self):
        if not self.is_running: return
        
        i = self.current_stage
        self.log_message.emit(f"Running Stage {i}/{self.max_stages}")
        
        # Config & Hardware Refresh
        try:
            self.config_manager.modify_dac_config(i)
            self.config_manager.modify_power_config(i)
            self.window.apply_dac_config()
            self.window.apply_power_config()
        except Exception as e:
            self.log_message.emit(f"Config Error: {e}")
            self.abort_test("Config Error")
            return

        # Calc Params
        try:
            # Check if stage config exists in cp_test_config.yaml
            stage_cfg = {}
            if self.cp_config and 'stages' in self.cp_config:
                stage_cfg = self.cp_config['stages'].get(i)
            
            if stage_cfg:
                start_v = float(stage_cfg.get('start', -0.5))
                step_v = float(stage_cfg.get('step', 0.01))
                points = int(stage_cfg.get('points', 100))
                self.log_message.emit(f"Using Config Params for Stage {i}: Start={start_v}, Step={step_v}, Points={points}")
            else:
                # Fallback to auto-calculation
                start_v, step_v, points = self.sequencer.calculate_scan_params(i)
                self.log_message.emit(f"Using Auto-Calculated Params for Stage {i}: Start={start_v:.4f}, Step={step_v:.6f}, Points={points}")
                
        except Exception as e:
            self.log_message.emit(f"Param Error: {e}")
            self.abort_test("Param Error")
            return

        # Setup GUI params for the test
        self.window.txt_start.setText(f"{start_v:.4f}")
        self.window.txt_step.setText(f"{step_v:.6f}")
        self.window.txt_points.setText(str(points))
        if not self.window.rb_dac.isChecked():
            self.window.rb_dac.setChecked(True)
            
        # Set DAC/Multimeter from config or defaults
        dac_alias = "DAC1"
        dac_ch = "0"
        dm_alias = "DM1"
        
        if self.cp_config:
            dac_alias = self.cp_config.get('dac_alias', "DAC1")
            dac_ch = str(self.cp_config.get('dac_channel', "0"))
            dm_alias = self.cp_config.get('multimeter_alias', "DM1")
        
        self.window.combo_dac_sel_lin.setCurrentText(dac_alias) 
        self.window.txt_dac_ch.setText(dac_ch)
        self.window.combo_dm_sel.setCurrentText(dm_alias)

        # Start Test
        self.window.start_linearity_test()
        
        if hasattr(self.window, 'lin_worker') and self.window.lin_worker:
            self.window.lin_worker.finished_signal.connect(self.on_stage_finished)
        else:
            self.abort_test("Worker Error")

    def on_stage_finished(self):
        try:
            self.window.lin_worker.finished_signal.disconnect(self.on_stage_finished)
        except:
            pass
            
        if not self.is_running: return

        # Collect Results for this stage
        metrics = self.read_latest_stage_result()
        
        prefix = f'S{self.current_stage}'
        # self.test_data[f'{prefix}_Gain_Config'] = self.sequencer.gain_map.get(self.current_stage) # Removed per request
        self.test_data[f'{prefix}_Input_Amp'] = float(self.window.txt_start.text().replace('-','')) # approx
        
        # Measure DP Current for this stage (Requirement 1)
        key = f'{prefix}_DP_Current' # Default key
        curr_val = None
        try:
            # Determine which DP/Channel to measure based on cp_hardware_config
            hw_config = self.config_manager.get_cp_hardware_config()
            stage_cfg = hw_config.get('stages', {}).get(self.current_stage, {})
            power_updates = stage_cfg.get('power', {})
            
            target_dp_name = "DP1" # Default fallback
            target_ch = 2 # Default fallback
            
            # If power updates exist for this stage, use the first one found
            if power_updates:
                # power_updates structure: {'DP1': {2: 1.9}}
                for dp_name, channels in power_updates.items():
                    if channels:
                        for ch, _ in channels.items():
                            target_dp_name = dp_name
                            try:
                                target_ch = int(ch)
                            except:
                                target_ch = ch
                            key = f'{prefix}_{target_dp_name}_CH{target_ch}' # Update key
                            break # Take first channel of this instrument
                    break # Take first instrument found

            dp = self.window.inst_mgr.get_instrument(target_dp_name)
            if dp and dp.connected:
                curr = dp.measure_current(target_ch)
                self.test_data[key] = curr
                curr_val = curr
                self.log_message.emit(f"Stage {self.current_stage} {target_dp_name} CH{target_ch} Current: {curr:.4f}A")
            else:
                self.test_data[key] = "N/A"
        except Exception as e:
            self.log_message.emit(f"Error measuring DP current: {e}")
            self.test_data[key] = "Error"

        stage_result = 'PASS'
        
        # Stage Current Check (Requirement 2)
        if curr_val is not None:
            stage_current_limits = self.config_manager.get_stage_current_limits()
            stage_limit = stage_current_limits.get(f'stage{self.current_stage}')
            
            if stage_limit:
                try:
                    min_c = float(stage_limit.get('min_current', -float('inf')))
                    max_c = float(stage_limit.get('max_current', float('inf')))
                    
                    if not (min_c <= curr_val <= max_c):
                        self.log_message.emit(f"FAIL: Stage {self.current_stage} Current {curr_val:.4f}A out of range ({min_c}, {max_c})")
                        stage_result = 'FAIL'
                        
                        if ABORT_ON_STAGE_CURRENT_FAIL:
                            self.log_message.emit("Aborting test due to Stage Current failure.")
                            self.test_data['Final_Result'] = 'FAIL'
                            self.test_data['Fail_Reason'] = f'Stage{self.current_stage}_Current'
                            self.test_data[f'{prefix}_Result'] = stage_result
                            self.finish_test()
                            return
                        else:
                            self.log_message.emit("Continuing test despite Stage Current failure (Debug Mode).")
                except Exception as e:
                    self.log_message.emit(f"Error checking stage current limit: {e}")
        
        if metrics:
            self.test_data[f'{prefix}_Gain'] = metrics.get('Gain', 0)
            self.test_data[f'{prefix}_Offset'] = metrics.get('Offset', 0)
            self.test_data[f'{prefix}_No_Linearity'] = metrics.get('Nonlinearity', 0)
            self.test_data[f'{prefix}_Max_INL'] = metrics.get('Max_INL', 0)
            self.test_data[f'{prefix}_Max_DNL'] = metrics.get('Max_DNL', 0)
            
            # Check Nonlinearity Limit
            nl = metrics.get('Nonlinearity', 0)
            if nl > NO_LINEARITY_LIMIT:
                self.log_message.emit(f"FAIL: Stage {self.current_stage} Nonlinearity {nl:.4f}% > {NO_LINEARITY_LIMIT}%.")
                stage_result = 'FAIL'
                
                if ABORT_ON_NONLINEARITY_FAIL:
                    self.log_message.emit("Aborting test due to Nonlinearity failure.")
                    self.test_data['Final_Result'] = 'FAIL'
                    self.test_data['Fail_Reason'] = f'Stage{self.current_stage}_Linearity'
                    self.test_data[f'{prefix}_Result'] = stage_result
                    self.finish_test()
                    return
                else:
                    self.log_message.emit("Continuing test despite Nonlinearity failure (Debug Mode).")
        else:
            stage_result = 'FAIL'
            self.log_message.emit(f"FAIL: Stage {self.current_stage} No metrics found.")
        
        self.test_data[f'{prefix}_Result'] = stage_result

        # Update Final Result if this stage failed
        if stage_result == 'FAIL':
            self.test_data['Final_Result'] = 'FAIL'
            if not self.test_data['Fail_Reason']:
                 self.test_data['Fail_Reason'] = f'Stage{self.current_stage}_Fail'

        self.current_stage += 1
        if self.current_stage <= self.max_stages:
            QTimer.singleShot(500, self.run_stage)
        else:
            if self.test_data['Final_Result'] == 'PENDING':
                self.test_data['Final_Result'] = 'PASS'
            self.finish_test()

    def read_latest_stage_result(self):
        # Helper to parse the last generated result file
        import os
        folder = "results/dc_linearity_result"
        if self.site_id:
             folder = f"{folder}/{self.site_id}"
             
        if not os.path.exists(folder): 
            self.log_message.emit(f"Error: Result folder {folder} not found.")
            return None
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.txt')]
        if not files: 
            self.log_message.emit("Error: No result files found.")
            return None
        latest = max(files, key=os.path.getctime)
        
        metrics = {}
        try:
            # Try reading with utf-8 first, then fallback to gbk or ignore errors
            content = ""
            try:
                with open(latest, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(latest, 'r', encoding='gbk', errors='ignore') as f:
                    content = f.read()

            import re
            
            # Regex for new fields
            # Gain (Vout/Vin)               : 0.999999
            # Offset                        : 0.000001 V
            # Nonlinearity                  : 0.0010 % FSR
            
            gain = re.search(r"Gain \(Vout/Vin\)[\s:]+([-\d\.]+)", content)
            offset = re.search(r"Offset[\s:]+([-\d\.]+)", content)
            nl = re.search(r"Nonlinearity[\s:]+([-\d\.]+)", content)
            
            inl = re.search(r"Max INL\s*:\s*([-\d\.]+)", content)
            dnl = re.search(r"Max DNL\s*:\s*([-\d\.]+)", content)
            
            if gain: metrics['Gain'] = float(gain.group(1))
            if offset: metrics['Offset'] = float(offset.group(1))
            if nl: metrics['Nonlinearity'] = float(nl.group(1))
            if inl: metrics['Max_INL'] = float(inl.group(1))
            if dnl: metrics['Max_DNL'] = float(dnl.group(1))
            
            # Ensure Max_INL and Max_DNL are parsed correctly. 
            # If they are not found in the file, they might be 0 or missing.
            # The regex looks for "Max INL: 0.0000" or "Max INL= 0.0000"
            if 'Max_INL' not in metrics:
                self.log_message.emit("Warning: Max INL not found in result file.")
            if 'Max_DNL' not in metrics:
                self.log_message.emit("Warning: Max DNL not found in result file.")
            
            if not metrics:
                self.log_message.emit(f"Warning: No metrics parsed from {latest}")

        except Exception as e:
            self.log_message.emit(f"Error reading result file {latest}: {e}")
            pass
        return metrics

    def abort_test(self, reason):
        self.is_running = False
        self.test_data['Final_Result'] = 'FAIL'
        self.test_data['Fail_Reason'] = reason
        
        # Stop Linearity Worker if running to avoid race conditions with instruments
        if hasattr(self.window, 'lin_worker') and self.window.lin_worker and self.window.lin_worker.isRunning():
            self.log_message.emit("Stopping active scan...")
            # Disconnect existing connections to avoid on_stage_finished logic
            try:
                self.window.lin_worker.finished_signal.disconnect() 
            except:
                pass
            
            # Connect finish_test to run after worker stops
            self.window.lin_worker.finished_signal.connect(self.finish_test)
            self.window.lin_worker.stop()
        else:
            self.finish_test()

    def safe_power_down(self):
        """
        Executes a safe power down sequence by reverting stages in reverse order.
        """
        self.log_message.emit("Initiating Safe Power Down Sequence...")
        
        # Determine start stage (current stage might be running or finished)
        # If current_stage is 8 (finished 7), start from 7.
        start_stage = self.current_stage
        if start_stage > self.max_stages:
            start_stage = self.max_stages
            
        for i in range(start_stage, 0, -1):
            self.log_message.emit(f"Reverting Stage {i}...")
            
            # 1. Revert DAC changes of Stage i
            self.config_manager.revert_dac_changes(i)
            self.window.apply_dac_config()
            
            # 2. Apply Power Config of Stage i-1
            if i > 1:
                self.config_manager.modify_power_config(i - 1)
                self.window.apply_power_config()
            else:
                # i=1, target is Stage 0 (Initial)
                self.config_manager.reset_power_to_initial()
                self.window.apply_power_config()
            
            # Optional: Wait a bit
            time.sleep(0.5)
            
        self.log_message.emit("Safe Power Down: Returned to Initial State.")
        self.window.start_power_off()

    def finish_test(self):
        self.log_message.emit("Test Finished. Executing Safe Power Down...")
        self.safe_power_down()
        
        # Save Data
        if not self.data_manager.save_result(self.test_data):
            self.log_message.emit("CRITICAL ERROR: Failed to save results! Please close Wafer_Sort_Results.csv and try again.")
            # We could add a retry mechanism or a popup here if needed, 
            # but for now logging is the first step.
            
        self.finished.emit(self.test_data)
        self.is_running = False
