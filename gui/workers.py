from PySide6.QtCore import QThread, Signal
from core import test_logic

class PowerWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()
    
    def __init__(self, instrument_manager, mode="ON"):
        super().__init__()
        self.logic = test_logic.PowerTestLogic(instrument_manager)
        self.mode = mode # "ON" or "OFF"
        self.context = None

    def run(self):
        # Create a context that bridges logic callbacks to Qt Signals
        self.context = test_logic.TestContext(
            log_callback=self.log_signal.emit,
            progress_callback=None
        )
        
        self.logic.run_power_sequence(self.context, mode=self.mode)
        self.finished_signal.emit()

    def stop(self):
        if self.context:
            self.context.request_stop()

class LinearityWorker(QThread):
    progress_signal = Signal(int)
    log_signal = Signal(str)
    result_signal = Signal(object, object, object) # input_vals, meas_vals, metrics
    finished_signal = Signal()

    def __init__(self, instrument_manager, source_type, start_v, step_v, points, dac_alias, dac_ch, dm_alias, dg_alias):
        super().__init__()
        self.logic = test_logic.LinearityTestLogic(instrument_manager)
        self.source_type = source_type
        self.start_v = start_v
        self.step_v = step_v
        self.points = points
        self.dac_alias = dac_alias
        self.dac_ch = dac_ch
        self.dm_alias = dm_alias
        self.dg_alias = dg_alias
        self.context = None

    def run(self):
        self.context = test_logic.TestContext(
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
            self.dg_alias
        )
        
        if results:
            input_vals, measured_vals, metrics = results
            if metrics:
                self.result_signal.emit(input_vals, measured_vals, metrics)

        self.finished_signal.emit()

    def stop(self):
        if self.context:
            self.context.request_stop()
