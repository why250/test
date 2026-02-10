import math
import os
from PySide6.QtCore import QObject, QTimer
from .config_manager import ConfigManager

# Safety Limit for Input Amplitude (Volts)
VIN_SAFETY_LIMIT = 0.5

class AutoTestSequencer(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.config_manager = ConfigManager()
        self.current_stage = 1
        self.max_stages = 7
        self.result_folder = "results/dc_linearity_result"
        
        # Gain table from SRS v3.0
        # Stage: Gain(dB)
        self.gain_map = {
            1: -9.6,
            2: -3.6,
            3: 0,
            4: 2,
            5: 4,
            6: 6,
            7: 8
        }

    def start(self):
        print("=== Starting Automated Test Sequence (SRS v3.0) ===")
        
        # 1. Connect Devices (REQ-01)
        print("Connecting devices...")
        self.window.connect_all_devices()
        
        # Check connections (REQ-02)
        # We can check if inst_mgr has connected instruments
        # For simplicity, we assume connect_all_devices logs errors.
        # Ideally, we should verify connection status here.
        if not self._check_connections():
            print("Error: Device connection failed. Aborting.")
            return

        # 2. Power On Sequence (REQ-03)
        print("Executing Power On Sequence...")
        self.window.start_power_on()
        
        # Wait for Power On to complete. 
        # Since start_power_on is async (Worker), we need to wait.
        # We can hook into pwr_worker if it exists, or just wait a fixed time if we can't hook easily.
        # Better: hook into finished signal.
        if hasattr(self.window, 'pwr_worker') and self.window.pwr_worker:
             self.window.pwr_worker.finished_signal.connect(self.on_power_on_finished)
        else:
            # Fallback if worker not ready immediately (should be created in start_power_on)
            # But start_power_on creates it.
            # We need to access it *after* it's created.
            # Let's use a small delay to attach signal.
            QTimer.singleShot(500, self._attach_power_on_signal)

    def _check_connections(self):
        # Simple check: do we have DP1, DAC1, DM1?
        required = ['DP1', 'DAC1', 'DM1']
        connected = self.window.inst_mgr.instruments
        for req in required:
            inst = connected.get(req)
            if not inst or not inst.connected:
                print(f"Missing connection: {req}")
                return False
        return True

    def _attach_power_on_signal(self):
        if hasattr(self.window, 'pwr_worker') and self.window.pwr_worker:
            self.window.pwr_worker.finished_signal.connect(self.on_power_on_finished)
        else:
            print("Warning: Could not attach to Power Worker. Proceeding with delay.")
            QTimer.singleShot(5000, self.run_stage)

    def on_power_on_finished(self):
        print("Power On Sequence Completed.")
        try:
            self.window.pwr_worker.finished_signal.disconnect(self.on_power_on_finished)
        except:
            pass
        
        # REQ-04: Current Check
        print("Checking Current Limits (REQ-04)...")
        self.check_current_limits()

        # Start Loop Test (REQ-03 -> 3.3)
        QTimer.singleShot(2000, self.run_stage)

    def check_current_limits(self):
        """
        Reads actual current from all channels defined in Power_limit_config.
        Checks if they are within limits.
        Logs FAIL if not, but does not stop (as per user request).
        """
        limits = self.config_manager.get_power_limits()
        if not limits:
            print("No limits found in Power_limit_config.yaml.")
            return

        all_pass = True
        print(f"{'Instrument':<10} {'Channel':<8} {'Measured':<10} {'Limit (Min, Max)':<20} {'Status':<10}")
        print("-" * 70)

        for limit in limits:
            inst_name = limit.get('instrument')
            try:
                channel = int(limit.get('channel'))
            except:
                continue
                
            min_c = float(limit.get('min_current', -float('inf')))
            max_c = float(limit.get('max_current', float('inf')))

            # Get Instrument
            inst = self.window.inst_mgr.get_instrument(inst_name)
            if not inst or not inst.connected:
                print(f"{inst_name:<10} {channel:<8} {'N/A':<10} {f'({min_c}, {max_c})':<20} {'N/A (Not Connected)':<10}")
                continue

            try:
                # Measure Current
                measured = inst.measure_current(channel)
                
                # Check Limit
                status = "PASS"
                if not (min_c <= measured <= max_c):
                    status = "FAIL"
                    all_pass = False
                
                print(f"{inst_name:<10} {channel:<8} {measured:<10.4f} {f'({min_c}, {max_c})':<20} {status:<10}")

            except Exception as e:
                print(f"{inst_name:<10} {channel:<8} {'Error':<10} {f'({min_c}, {max_c})':<20} {str(e):<10}")
        
        print("-" * 70)
        if not all_pass:
            print("Warning: Some current checks FAILED. Continuing test as per configuration.")
        else:
            print("All current checks PASSED.")


    def run_stage(self):
        i = self.current_stage
        print(f"\n--- Running Stage {i}/{self.max_stages} ---")
        
        # 3.3.2 Dynamic Config Modification (REQ-06, REQ-07)
        try:
            self.config_manager.modify_dac_config(i)
            self.config_manager.modify_power_config(i)
        except Exception as e:
            print(f"Error modifying configs: {e}")
            self.abort_sequence()
            return

        # 3.3.2 Hardware Refresh (REQ-08)
        print("Loading DAC Configuration...")
        self.window.apply_dac_config()
        
        print("Loading Power Configuration...")
        self.window.apply_power_config()
        
        # 3.3.3 Calculate Scan Parameters (REQ-09, REQ-10)
        try:
            start_v, step_v, points = self.calculate_scan_params(i)
            print(f"Calculated Params: Start={start_v:.4f}V, Step={step_v:.6f}V, Points={points}")
        except Exception as e:
            print(f"Error calculating parameters: {e}")
            self.abort_sequence()
            return
        
        # Set GUI Controls
        self.window.txt_start.setText(f"{start_v:.4f}")
        self.window.txt_step.setText(f"{step_v:.6f}")
        self.window.txt_points.setText(str(points))
        
        # Ensure correct source selection (DAC)
        if not self.window.rb_dac.isChecked():
            self.window.rb_dac.setChecked(True)
            
        # Set Channels (Fixed DAC CH10 as per SRS v2.0? SRS v3.0 doesn't explicitly mention CH10 in text but implies consistency)
        # SRS v3.0 REQ-11 says "Control DAC/DG". Assuming DAC CH10 from previous context.
        self.window.combo_dac_sel_lin.setCurrentText("DAC1") 
        self.window.txt_dac_ch.setText("10")
        
        # 3.3.4 Execute Test (REQ-11)
        print("Starting Linearity Test...")
        self.window.start_linearity_test()
        
        # Wait for Completion
        if hasattr(self.window, 'lin_worker') and self.window.lin_worker:
            self.window.lin_worker.finished_signal.connect(self.on_stage_finished)
        else:
            print("Error: LinearityWorker not found.")
            self.abort_sequence()

    def calculate_scan_params(self, stage_index):
        """
        REQ-09, REQ-10
        Target Output = +/- 0.25V
        G_lin = 10^(Gain_dB / 20)
        V_in_amp = 0.25 / G_lin
        Start = -V_in_amp
        Points = 101
        Step = (2 * V_in_amp) / (101 - 1)
        """
        gain_db = self.gain_map.get(stage_index, 0)
        g_lin = 10 ** (gain_db / 20.0)
        v_in_amp = 0.25 / g_lin
        
        # Safety Check (Exception Handling Strategy)
        if v_in_amp > VIN_SAFETY_LIMIT:
            print(f"Warning: Calculated Input Amplitude {v_in_amp:.2f}V exceeds safety limit ({VIN_SAFETY_LIMIT}V). Clamping to +/-{VIN_SAFETY_LIMIT}V.")
            v_in_amp = VIN_SAFETY_LIMIT

        start_v = -v_in_amp
        points = 101
        step_v = (2 * v_in_amp) / (points - 1)
        
        return start_v, step_v, points

    def on_stage_finished(self):
        print(f"Stage {self.current_stage} Analysis Completed.")
        
        try:
            self.window.lin_worker.finished_signal.disconnect(self.on_stage_finished)
        except:
            pass
        
        # REQ-12: Save Data (Rename with Stage)
        self.tag_latest_result()

        # Proceed
        self.current_stage += 1
        if self.current_stage <= self.max_stages:
            QTimer.singleShot(2000, self.run_stage)
        else:
            self.finish_sequence()

    def finish_sequence(self):
        # REQ-13, REQ-14, REQ-15
        print("\n=== All 7 Stages Completed ===")
        print("Executing Power Off Sequence...")
        self.window.start_power_off()
        print("Automation Finished.")

    def abort_sequence(self):
        print("Aborting sequence due to error.")
        print("Executing Emergency Power Off...")
        self.window.start_power_off()

    def tag_latest_result(self):
        """
        Finds the most recently created result file and renames it with Stage prefix.
        Handles both .txt results and .png plots.
        """
        # 1. Handle Text Result
        if os.path.exists(self.result_folder):
            files = [os.path.join(self.result_folder, f) for f in os.listdir(self.result_folder) if f.endswith('.txt')]
            if files:
                latest_file = max(files, key=os.path.getctime)
                dirname, basename = os.path.split(latest_file)
                if not basename.startswith("Stage"):
                    new_name = f"Stage{self.current_stage}_{basename}"
                    new_path = os.path.join(dirname, new_name)
                    try:
                        os.rename(latest_file, new_path)
                        print(f"Result saved as: {new_name}")
                    except Exception as e:
                        print(f"Error renaming result file: {e}")

        # 2. Handle Image Plot
        image_folder = "image"
        if os.path.exists(image_folder):
            files = [os.path.join(image_folder, f) for f in os.listdir(image_folder) if f.endswith('.png')]
            if files:
                latest_file = max(files, key=os.path.getctime)
                dirname, basename = os.path.split(latest_file)
                if not basename.startswith("Stage"):
                    new_name = f"Stage{self.current_stage}_{basename}"
                    new_path = os.path.join(dirname, new_name)
                    try:
                        os.rename(latest_file, new_path)
                        print(f"Plot saved as: {new_name}")
                    except Exception as e:
                        print(f"Error renaming plot file: {e}")
