from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QCheckBox, QGroupBox, 
                               QTextEdit, QMessageBox)
from PySide6.QtCore import Qt, Slot
from .mapping_manager import MappingManager
from .test_logic import CPTestRunner
from .visualization import WaferMapGenerator

class CPTestWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.mapping_mgr = MappingManager()
        self.map_gen = WaferMapGenerator()
        self.runner = None
        
        self.setup_ui()
        self.update_coordinates()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Site Management Group
        grp_site = QGroupBox("Site Management")
        site_layout = QHBoxLayout()
        
        site_layout.addWidget(QLabel("Site ID:"))
        self.txt_site_id = QLineEdit(str(self.mapping_mgr.current_site_id))
        self.txt_site_id.returnPressed.connect(self.on_site_id_changed)
        site_layout.addWidget(self.txt_site_id)
        
        self.lbl_coords = QLabel("Coords: R: - , C: -")
        self.lbl_coords.setStyleSheet("font-weight: bold; color: blue;")
        site_layout.addWidget(self.lbl_coords)
        
        self.chk_auto_inc = QCheckBox("Auto Increment Site ID")
        self.chk_auto_inc.setChecked(True)
        site_layout.addWidget(self.chk_auto_inc)
        
        grp_site.setLayout(site_layout)
        layout.addWidget(grp_site)

        # 2. Control Group
        grp_ctrl = QGroupBox("Test Control")
        ctrl_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("Start CP Test")
        self.btn_start.clicked.connect(self.start_test)
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        ctrl_layout.addWidget(self.btn_start)
        
        self.btn_gen_map = QPushButton("Generate Wafer Map")
        self.btn_gen_map.clicked.connect(self.generate_map)
        ctrl_layout.addWidget(self.btn_gen_map)
        
        grp_ctrl.setLayout(ctrl_layout)
        layout.addWidget(grp_ctrl)

        # 3. Log Area
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        layout.addWidget(QLabel("Test Log:"))
        layout.addWidget(self.txt_log)

    def log(self, msg):
        self.txt_log.append(msg)

    def on_site_id_changed(self):
        try:
            site_id = int(self.txt_site_id.text())
            if self.mapping_mgr.set_current_site(site_id):
                self.update_coordinates()
            else:
                self.lbl_coords.setText("Coords: Invalid Site ID")
        except ValueError:
            pass

    def update_coordinates(self):
        site_id = self.mapping_mgr.current_site_id
        coords = self.mapping_mgr.get_coordinates(site_id)
        if coords:
            self.lbl_coords.setText(f"Coords: R: {coords[0]}, C: {coords[1]}")
            self.txt_site_id.setText(str(site_id))
        else:
            self.lbl_coords.setText("Coords: Not Found")

    def start_test(self):
        site_id = self.mapping_mgr.current_site_id
        coords = self.mapping_mgr.get_coordinates(site_id)
        
        if not coords:
            QMessageBox.warning(self, "Error", "Invalid Site ID or Mapping not found.")
            return

        self.btn_start.setEnabled(False)
        self.log(f"--- Starting Test for Site {site_id} ---")
        
        # Initialize Runner
        self.runner = CPTestRunner(self.main_window, site_id, coords[0], coords[1])
        self.runner.log_message.connect(self.log)
        self.runner.finished.connect(self.on_test_finished)
        self.runner.start()

    def on_test_finished(self, result_data):
        self.btn_start.setEnabled(True)
        res = result_data.get('Final_Result', 'UNKNOWN')
        self.log(f"Test Finished. Result: {res}")
        
        if self.chk_auto_inc.isChecked():
            next_id = self.mapping_mgr.get_next_site_id()
            if next_id:
                self.mapping_mgr.set_current_site(next_id)
                self.update_coordinates()
                self.log(f"Auto-incremented to Site {next_id}")
            else:
                self.log("No next site found in mapping.")

    def generate_map(self):
        path = self.map_gen.generate_static_map()
        if path:
            self.log(f"Map generated: {path}")
            QMessageBox.information(self, "Success", f"Wafer Map saved to:\n{path}")
        else:
            self.log("Failed to generate map (No data?)")
            QMessageBox.warning(self, "Error", "Failed to generate map.")
