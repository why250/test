from PySide6.QtCore import QThread, Signal
from core import PowerTestLogic, LinearityTestLogic, TPTestLogic, TestContext
from core import utils

class PowerWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()
    
    def __init__(self, instrument_manager, mode="ON", site_id=None):
        super().__init__()
        self.logic = PowerTestLogic(instrument_manager)
        self.mode = mode # "ON" or "OFF"
        self.site_id = site_id
        self.context = None

    def run(self):
        # Create a context that bridges logic callbacks to Qt Signals
        self.context = TestContext(
            log_callback=self.log_signal.emit,
            progress_callback=None
        )
        
        self.logic.run_power_sequence(self.context, mode=self.mode, site_id=self.site_id)
        self.finished_signal.emit()

    def stop(self):
        if self.context:
            self.context.request_stop()

class LinearityWorker(QThread):
    progress_signal = Signal(int)
    log_signal = Signal(str)
    result_signal = Signal(object, object, object, object) # input_vals, meas_vals, metrics, site_id
    finished_signal = Signal()

    def __init__(self, instrument_manager, source_type, start_v, step_v, points, dac_alias, dac_ch, dm_alias, dg_alias, site_id=None):
        super().__init__()
        self.logic = LinearityTestLogic(instrument_manager)
        self.source_type = source_type
        self.start_v = start_v
        self.step_v = step_v
        self.points = points
        self.dac_alias = dac_alias
        self.dac_ch = dac_ch
        self.dm_alias = dm_alias
        self.dg_alias = dg_alias
        self.site_id = site_id
        self.context = None

    def run(self):
        self.context = TestContext(
            log_callback=self.log_signal.emit,
            progress_callback=self.progress_signal.emit
        )
        
        results = self.logic.run_test(
            self.context, 
            self.source_type, 
            self.start_v, 
            self.step_v, 
            self.points, 
            self.dac_alias, 
            self.dac_ch,
            self.dm_alias,
            self.dg_alias,
            self.site_id
        )
        
        if results:
            input_vals, measured_vals, metrics = results
            if metrics:
                self.result_signal.emit(input_vals, measured_vals, metrics, self.site_id)

        self.finished_signal.emit()

    def stop(self):
        if self.context:
            self.context.request_stop()


class TPTestWorker(QThread):
    progress_signal = Signal(int)
    log_signal = Signal(str)
    result_signal = Signal(object)  # list of {"name", "port", "voltage"}
    finished_signal = Signal()

    def __init__(self, instrument_manager, config_path="config/DMM_Config.yaml"):
        super().__init__()
        self.inst_mgr = instrument_manager
        self.config_path = config_path
        self.logic = TPTestLogic()
        self.context = None

    def run(self):
        self.context = TestContext(
            log_callback=self.log_signal.emit,
            progress_callback=self.progress_signal.emit
        )

        cfg = utils.load_yaml_config(self.config_path)
        if not cfg:
            self.log_signal.emit(f"Error: Cannot load {self.config_path}")
            self.finished_signal.emit()
            return

        serial_alias = cfg.get("serial_alias", "")
        dm_alias = cfg.get("dm_alias", "")
        test_points = cfg.get("test_points", {})

        if not serial_alias or not dm_alias or not test_points:
            self.log_signal.emit("Error: DMM_Config.yaml is missing required fields.")
            self.finished_signal.emit()
            return

        serial_inst = self.inst_mgr.get_instrument(serial_alias)
        if not serial_inst:
            self.log_signal.emit(f"Error: Serial instrument '{serial_alias}' not found.")
            self.finished_signal.emit()
            return
        if not serial_inst.connected:
            if not serial_inst.connect():
                self.log_signal.emit(f"Failed to connect to '{serial_alias}'.")
                self.finished_signal.emit()
                return

        dm = self.inst_mgr.get_instrument(dm_alias)
        if not dm:
            self.log_signal.emit(f"Error: Multimeter '{dm_alias}' not found.")
            self.finished_signal.emit()
            return
        if not dm.connected:
            if not dm.connect():
                self.log_signal.emit(f"Failed to connect to '{dm_alias}'.")
                self.finished_signal.emit()
                return

        results = self.logic.run_test(self.context, serial_inst, dm, test_points)
        self.result_signal.emit(results)
        self.finished_signal.emit()

    def stop(self):
        if self.context:
            self.context.request_stop()
