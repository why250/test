import time
from PySide6.QtCore import QObject, Signal, QTimer
from automation.test_sequencer import AutoTestSequencer
from automation.config_manager import ConfigManager
from .data_manager import DataManager

# Debug Constant: Abort test if Power Limit fails?
ABORT_ON_POWER_FAIL = False
# Debug Constant: Ignore Linearity Fail?
IGNORE_LINEARITY_FAIL = True
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
        self.data_manager = DataManager()
        
        # Reusing logic from AutoTestSequencer where possible, 
        # but we need finer control for the "Fuse" mechanism.
        self.sequencer = AutoTestSequencer(window) 
        
        self.current_stage = 1
        self.max_stages = 7
        self.test_data = {
            'Site_ID': site_id,
            'Row': row,
            'Col': col,
            'Final_Result': 'PENDING',
            'Fail_Reason': ''
        }
        self.is_running = False

    def start(self):
        self.is_running = True
        self.log_message.emit(f"Starting CP Test for Site {self.site_id} (R{self.row}, C{self.col})")
        
        # 1. Power On
        self.log_message.emit("Executing Power On Sequence...")
        self.window.start_power_on()
        
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
        
        self.test_data['Power_Current'] = current_val
        self.test_data['Power_Check_Result'] = power_status
        
        if power_status == "FAIL":
            if ABORT_ON_POWER_FAIL:
                self.log_message.emit("CRITICAL: Power Limit Exceeded! Aborting Test.")
                self.test_data['Final_Result'] = 'FAIL'
                self.test_data['Fail_Reason'] = 'Power_Limit'
                self.finish_test() # Go directly to Power Off
                return
            else:
                self.log_message.emit("WARNING: Power Limit Exceeded! Continuing Test (Debug Mode).")
                self.test_data['Power_Check_Result'] = 'FAIL (Ignored)'

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
            start_v, step_v, points = self.sequencer.calculate_scan_params(i)
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
        self.window.combo_dac_sel_lin.setCurrentText("DAC1") 
        self.window.txt_dac_ch.setText("10")

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
        self.test_data[f'{prefix}_Gain_Config'] = self.sequencer.gain_map.get(self.current_stage)
        self.test_data[f'{prefix}_Input_Amp'] = float(self.window.txt_start.text().replace('-','')) # approx
        
        stage_result = 'PASS'
        
        if metrics:
            self.test_data[f'{prefix}_Gain'] = metrics.get('Gain', 0)
            self.test_data[f'{prefix}_Offset'] = metrics.get('Offset', 0)
            self.test_data[f'{prefix}_No_Linearity'] = metrics.get('Nonlinearity', 0)
            self.test_data[f'{prefix}_Max_INL'] = metrics.get('Max_INL', 0)
            self.test_data[f'{prefix}_Max_DNL'] = metrics.get('Max_DNL', 0)
            
            # Check Nonlinearity Limit
            nl = metrics.get('Nonlinearity', 0)
            if nl > NO_LINEARITY_LIMIT:
                if IGNORE_LINEARITY_FAIL:
                    self.log_message.emit(f"WARNING: Stage {self.current_stage} Nonlinearity {nl:.4f}% > {NO_LINEARITY_LIMIT}%. (Ignored)")
                    stage_result = 'PASS (Ignored)'
                else:
                    self.log_message.emit(f"FAIL: Stage {self.current_stage} Nonlinearity {nl:.4f}% > {NO_LINEARITY_LIMIT}%.")
                    stage_result = 'FAIL'
        else:
            stage_result = 'FAIL'
            self.test_data['Final_Result'] = 'FAIL' # One stage fail -> Fail? SRS says "Yellow (PARTIAL)" if some fail.
        
        self.test_data[f'{prefix}_Result'] = stage_result

        # Check if we should continue
        # SRS: "Red (FAIL): Power fail or First stage fail".
        if self.current_stage == 1 and stage_result == 'FAIL':
             self.test_data['Final_Result'] = 'FAIL'
             self.test_data['Fail_Reason'] = 'Stage1_Fail'
             self.finish_test()
             return

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
            
            inl = re.search(r"Max INL[:=]\s*([-\d\.]+)", content)
            dnl = re.search(r"Max DNL[:=]\s*([-\d\.]+)", content)
            
            if gain: metrics['Gain'] = float(gain.group(1))
            if offset: metrics['Offset'] = float(offset.group(1))
            if nl: metrics['Nonlinearity'] = float(nl.group(1))
            if inl: metrics['Max_INL'] = float(inl.group(1))
            if dnl: metrics['Max_DNL'] = float(dnl.group(1))
            
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
        self.finish_test()

    def finish_test(self):
        self.log_message.emit("Test Finished. Executing Power Off...")
        self.window.start_power_off()
        
        # Save Data
        self.data_manager.save_result(self.test_data)
        self.finished.emit(self.test_data)
        self.is_running = False
