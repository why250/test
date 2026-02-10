import sys
import time
from datetime import datetime
import numpy as np

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QTextEdit, 
                               QTabWidget, QLineEdit, QCheckBox, QGroupBox, 
                               QRadioButton, QMessageBox, QProgressBar, QGridLayout,
                               QTreeWidget, QTreeWidgetItem, QHeaderView, QInputDialog, QComboBox)
from PySide6.QtCore import Qt, QThread

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.instruments import InstrumentManager
from core import utils
from .workers import PowerWorker, LinearityWorker
from cp_test.gui import CPTestWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automated Test System (PySide6)")
        self.resize(1100, 800)
        
        self.inst_mgr = InstrumentManager(simulation_mode=False)
        
        # Load instruments from visa.yaml if available
        visa_config = utils.load_yaml_config("visa.yaml")
        if visa_config and isinstance(visa_config, dict) and 'instruments' in visa_config:
            for inst in visa_config['instruments']:
                self.inst_mgr.register_instrument(inst['alias'], inst['type'], inst['address'])
        else:
            # Fallback / Demo
            self.inst_mgr.register_instrument("DP1", "DP", "USB0::0x1AB1::0xA4A8::DP2A265201089::INSTR")
            self.inst_mgr.register_instrument("DAC1", "DAC", "COM3")
            self.inst_mgr.register_instrument("DM1", "DM", "USB0::0xDEAD::0xBEEF::DM123::INSTR")
            self.inst_mgr.register_instrument("DG1", "DG", "USB0::0xDG::0xDG::DG123::INSTR")

        self.setup_ui()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top Bar: Connection & Mode
        top_layout = QHBoxLayout()
        self.chk_sim_mode = QCheckBox("Simulation Mode")
        self.chk_sim_mode.setChecked(False)
        self.chk_sim_mode.stateChanged.connect(self.toggle_sim_mode)
        top_layout.addWidget(self.chk_sim_mode)
        top_layout.addStretch()
        
        main_layout.addLayout(top_layout)
        
        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # 1. Connection Manager Tab (First Tab)
        self.setup_connection_tab()
        
        # 2. Power Control Tab
        self.setup_power_tab()
        
        # 3. Configuration Tab
        self.setup_config_tab()
        
        # 4. Linearity Test Tab
        self.setup_linearity_tab()
        
        # 5. CP Test Tab
        self.setup_cp_test_tab()
        
        # Log Area
        main_layout.addWidget(QLabel("System Log:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        main_layout.addWidget(self.log_text)

    def setup_connection_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Toolbar for Tree
        toolbar = QHBoxLayout()
        btn_add = QPushButton("Add Device")
        btn_add.clicked.connect(self.add_device_dialog)
        toolbar.addWidget(btn_add)
        
        btn_remove = QPushButton("Remove Device")
        btn_remove.clicked.connect(self.remove_selected_device)
        toolbar.addWidget(btn_remove)
        
        btn_connect_all = QPushButton("Connect All")
        btn_connect_all.clicked.connect(self.connect_all_devices)
        toolbar.addWidget(btn_connect_all)
        
        btn_disconnect_all = QPushButton("Disconnect All")
        btn_disconnect_all.clicked.connect(self.disconnect_all_devices)
        toolbar.addWidget(btn_disconnect_all)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Alias", "Type", "Address", "Status"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.tree)
        
        self.refresh_device_tree()
        
        self.tabs.addTab(tab, "Device Manager")

    def refresh_device_tree(self):
        self.tree.clear()
        instruments = self.inst_mgr.get_all_instruments()
        
        # Group by type
        groups = {
            "DP": QTreeWidgetItem(["Power Supplies"]),
            "DAC": QTreeWidgetItem(["DACs"]),
            "DM": QTreeWidgetItem(["Multimeters"]),
            "DG": QTreeWidgetItem(["Signal Generators"])
        }
        
        for key, item in groups.items():
            self.tree.addTopLevelItem(item)
            item.setExpanded(True)
            
        for alias, inst in instruments.items():
            # Determine type based on class name for simplicity or we should store type
            # In register_instrument we didn't store type explicitly in the object, 
            # but we can infer or store it. 
            # Let's infer from class name
            cls_name = inst.__class__.__name__
            type_key = "DP" if "PowerSupply" in cls_name else \
                       "DAC" if "DAC" in cls_name else \
                       "DM" if "Multimeter" in cls_name else \
                       "DG" if "SignalGenerator" in cls_name else "Other"
            
            if type_key in groups:
                status = "Connected" if inst.connected else "Disconnected"
                color = Qt.green if inst.connected else Qt.red
                
                # Handle different attribute names for address/port
                addr = getattr(inst, 'address', getattr(inst, 'port', 'Unknown'))
                
                item = QTreeWidgetItem([alias, type_key, addr, status])
                item.setForeground(3, color)
                groups[type_key].addChild(item)

    def add_device_dialog(self):
        # Simple dialog to add device
        # For a real app, create a custom QDialog. Here using QInputDialog sequences for brevity.
        types = ["DP", "DAC", "DM", "DG"]
        type_sel, ok = QInputDialog.getItem(self, "Add Device", "Select Type:", types, 0, False)
        if not ok: return
        
        alias, ok = QInputDialog.getText(self, "Add Device", "Enter Alias (e.g. DP2):")
        if not ok or not alias: return
        
        address, ok = QInputDialog.getText(self, "Add Device", "Enter Address (VISA or COM):")
        if not ok or not address: return
        
        self.inst_mgr.register_instrument(alias, type_sel, address)
        self.refresh_device_tree()
        self.log(f"Added device: {alias} ({type_sel}) at {address}")

    def remove_selected_device(self):
        item = self.tree.currentItem()
        if not item or item.parent() is None:
            return
            
        alias = item.text(0)
        self.inst_mgr.remove_instrument(alias)
        self.refresh_device_tree()
        self.log(f"Removed device: {alias}")

    def connect_all_devices(self):
        self.log("Connecting all devices...")
        instruments = self.inst_mgr.get_all_instruments()
        for alias, inst in instruments.items():
            if not inst.connected:
                if inst.connect():
                    self.log(f"Connected to {alias}")
                else:
                    self.log(f"Failed to connect to {alias}")
        self.refresh_device_tree()

    def disconnect_all_devices(self):
        self.log("Disconnecting all devices...")
        instruments = self.inst_mgr.get_all_instruments()
        for alias, inst in instruments.items():
            if inst.connected:
                inst.close()
                self.log(f"Disconnected {alias}")
        self.refresh_device_tree()

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")

    def toggle_sim_mode(self, state):
        is_sim = (state == 2) # 2 is Checked
        self.inst_mgr.simulation_mode = is_sim
        self.log(f"Simulation Mode set to: {is_sim}")
        # Re-connect logic might be needed if mode changes, but for now just log
        self.disconnect_all_devices()

    def setup_power_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        grp_ctrl = QGroupBox("Power Sequence Control")
        l_ctrl = QHBoxLayout(grp_ctrl)
        
        btn_on = QPushButton("Power ON Sequence")
        btn_on.clicked.connect(self.start_power_on)
        l_ctrl.addWidget(btn_on)
        
        btn_off = QPushButton("Power OFF Sequence")
        btn_off.clicked.connect(self.start_power_off)
        l_ctrl.addWidget(btn_off)
        
        layout.addWidget(grp_ctrl)
        layout.addStretch()
        self.tabs.addTab(tab, "Power Control")

    def setup_config_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # DAC Config
        grp_dac = QGroupBox("DAC Configuration")
        l_dac = QVBoxLayout(grp_dac)
        
        l_dac_row1 = QHBoxLayout()
        l_dac_row1.addWidget(QLabel("DAC Alias:"))
        self.combo_dac_sel = QComboBox() # Populate with DACs
        self.combo_dac_sel.setEditable(True)
        self.combo_dac_sel.addItem("DAC1")
        l_dac_row1.addWidget(self.combo_dac_sel)
        l_dac.addLayout(l_dac_row1)
        
        btn_load_dac = QPushButton("Load & Apply DAC_Config.csv")
        btn_load_dac.clicked.connect(self.apply_dac_config)
        l_dac.addWidget(btn_load_dac)
        
        layout.addWidget(grp_dac)
        
        # Power Config
        grp_pwr = QGroupBox("Power Configuration")
        l_pwr = QVBoxLayout(grp_pwr)
        
        btn_load_pwr = QPushButton("Load & Apply Power_Config.yaml")
        btn_load_pwr.clicked.connect(self.apply_power_config)
        l_pwr.addWidget(btn_load_pwr)
        
        layout.addWidget(grp_pwr)
        layout.addStretch()
        self.tabs.addTab(tab, "Configuration")

    def setup_linearity_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Left Panel: Settings
        left_panel = QWidget()
        l_left = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(300)
        
        grp_src = QGroupBox("Source Selection")
        l_src = QVBoxLayout(grp_src)
        self.rb_dac = QRadioButton("DAC")
        self.rb_dac.setChecked(True)
        self.rb_dg = QRadioButton("Signal Generator (DG)")
        l_src.addWidget(self.rb_dac)
        l_src.addWidget(self.rb_dg)
        l_left.addWidget(grp_src)
        
        grp_param = QGroupBox("Scan Parameters")
        l_param = QVBoxLayout(grp_param)
        
        l_param.addWidget(QLabel("Start Voltage (V):"))
        self.txt_start = QLineEdit("-0.2")
        l_param.addWidget(self.txt_start)
        
        l_param.addWidget(QLabel("Step (V):"))
        self.txt_step = QLineEdit("0.004")
        l_param.addWidget(self.txt_step)

        l_param.addWidget(QLabel("Points:"))
        self.txt_points = QLineEdit("101")
        l_param.addWidget(self.txt_points)

        # --- Dynamic Source Settings ---
        self.widget_dac_settings = QWidget()
        l_dac_settings = QVBoxLayout(self.widget_dac_settings)
        l_dac_settings.setContentsMargins(0, 0, 0, 0)
        
        l_dac_settings.addWidget(QLabel("DAC Alias:"))
        self.combo_dac_sel_lin = QComboBox()
        self.combo_dac_sel_lin.addItem("DAC1")
        self.combo_dac_sel_lin.setEditable(True)
        l_dac_settings.addWidget(self.combo_dac_sel_lin)

        l_dac_settings.addWidget(QLabel("DAC Channel:"))
        self.txt_dac_ch = QLineEdit("1")
        l_dac_settings.addWidget(self.txt_dac_ch)
        
        l_param.addWidget(self.widget_dac_settings)

        self.widget_dg_settings = QWidget()
        l_dg_settings = QVBoxLayout(self.widget_dg_settings)
        l_dg_settings.setContentsMargins(0, 0, 0, 0)

        l_dg_settings.addWidget(QLabel("Signal Generator Alias:"))
        self.combo_dg_sel = QComboBox()
        self.combo_dg_sel.addItem("DG1")
        self.combo_dg_sel.setEditable(True)
        l_dg_settings.addWidget(self.combo_dg_sel)

        l_dg_settings.addWidget(QLabel("DG Channel:"))
        self.txt_dg_ch = QLineEdit("1")
        l_dg_settings.addWidget(self.txt_dg_ch)

        l_param.addWidget(self.widget_dg_settings)
        
        # Connect signals to toggle visibility
        self.rb_dac.toggled.connect(self.update_source_visibility)
        self.rb_dg.toggled.connect(self.update_source_visibility)
        
        # Initialize visibility
        self.update_source_visibility()

        # --- Common Settings ---
        l_param.addWidget(QLabel("Multimeter Alias:"))
        self.combo_dm_sel = QComboBox()
        self.combo_dm_sel.addItem("DM1")
        self.combo_dm_sel.setEditable(True)
        l_param.addWidget(self.combo_dm_sel)

        l_left.addWidget(grp_param)
        
        self.btn_start_lin = QPushButton("Start Linearity Test")
        self.btn_start_lin.clicked.connect(self.start_linearity_test)
        l_left.addWidget(self.btn_start_lin)
        
        self.progress_bar = QProgressBar()
        l_left.addWidget(self.progress_bar)
        
        l_left.addStretch()
        layout.addWidget(left_panel)
        
        # Right Panel: Plot
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        self.tabs.addTab(tab, "Linearity Test")

    def setup_cp_test_tab(self):
        self.cp_test_widget = CPTestWidget(self)
        self.tabs.addTab(self.cp_test_widget, "CP Wafer Sort")

    def update_source_visibility(self):
        is_dac = self.rb_dac.isChecked()
        self.widget_dac_settings.setVisible(is_dac)
        self.widget_dg_settings.setVisible(not is_dac)

    # --- Slots ---

    def start_power_on(self):
        self.log("Starting Power ON Sequence...")
        # No longer need to pass address, logic uses registry
        self.pwr_worker = PowerWorker(self.inst_mgr, "ON")
        self.pwr_worker.log_signal.connect(self.log)
        self.pwr_worker.finished_signal.connect(lambda: self.log("Power ON Sequence Completed."))
        self.pwr_worker.start()

    def start_power_off(self):
        self.log("Starting Power OFF Sequence...")
        self.pwr_worker = PowerWorker(self.inst_mgr, "OFF")
        self.pwr_worker.log_signal.connect(self.log)
        self.pwr_worker.finished_signal.connect(lambda: self.log("Power OFF Sequence Completed."))
        self.pwr_worker.start()

    def apply_dac_config(self):
        self.log("Applying DAC Configuration...")
        configs = utils.load_csv_config("DAC_Config.csv")
        if not configs:
            self.log("Error: DAC_Config.csv not found or empty.")
            return
            
        dac_alias = self.combo_dac_sel.currentText()
        dac = self.inst_mgr.get_instrument(dac_alias)
        
        if not dac:
            self.log(f"Error: DAC '{dac_alias}' not found in registry. Please add it in Device Manager.")
            return
        
        if not dac.connected:
            if not dac.connect():
                self.log(f"Error: Could not connect to DAC '{dac_alias}'")
                return
            
        # Pre-process configs into a dictionary
        dac_data = {} 
        for item in configs:
            try:
                ch_name = item['Channel']
                ch_idx = int(ch_name.replace("DAC", ""))
                dac_data[ch_idx] = {
                    'range': float(item['Range']),
                    'voltage': float(item['Voltage'])
                }
            except Exception:
                continue

        # Process in chunks of 4 channels (Total 32 channels: 0-31)
        for i in range(0, 32, 4):
            chunk_indices = [i, i+1, i+2, i+3]
            
            # Prepare data for this chunk
            chunk_ranges = []
            
            # Check if any channel in this chunk is present in the config file
            # If so, we process the whole chunk (filling missing ones with defaults)
            # If the whole chunk is missing from config, we skip it
            chunk_has_data = any(idx in dac_data for idx in chunk_indices)
            if not chunk_has_data:
                continue

            for idx in chunk_indices:
                if idx in dac_data:
                    chunk_ranges.append(dac_data[idx]['range'])
                else:
                    chunk_ranges.append(2.5) # Default range

            # 1. Calculate and Send Range/Gear Command
            # Logic from config_loader.py
            dac_chip_num = 0 if i < 16 else 1
            register_addr = 13 - (i % 16) // 4
            
            gear_code = utils.calculate_gear_code(chunk_ranges)
            
            cmd_range = f"DAC{dac_chip_num:02d} {register_addr} {gear_code};"
            self.log(f"Set Range Group {i}-{i+3}: {cmd_range}")
            dac.send_raw_command(cmd_range)
            time.sleep(0.1)
            
            # 2. Send Output Commands for channels in this chunk
            for j, idx in enumerate(chunk_indices):
                if idx in dac_data:
                    v_range = chunk_ranges[j]
                    target_v = dac_data[idx]['voltage']
                    
                    code = utils.calculate_dac_code(str(v_range), target_v)
                    self.log(f"Set DAC{idx} ({v_range}V) to {target_v}V -> Code {code}")
                    dac.set_output(idx, code)
                    time.sleep(0.05)
        
        self.log("DAC Configuration Completed.")

    def apply_power_config(self):
        self.log("Applying Power Configuration...")
        configs = utils.load_yaml_config("Power_Config.yaml")
        if not configs:
            self.log("Error: Power_Config.yaml not found.")
            return
            
        # Logic needs to find DP by name in config, so we just ensure they are connected
        # Or we iterate configs and find the DP in registry
        
        for item in configs:
            try:
                dp_name = item['instrument']
                ch = item['channel']
                volt = float(item['voltage'])
                curr = float(item['current'])
                
                dp = self.inst_mgr.get_instrument(dp_name)
                if not dp:
                    self.log(f"Error: Power Supply '{dp_name}' not found in registry.")
                    continue
                    
                if not dp.connected:
                    dp.connect()
                
                self.log(f"Set {dp_name} CH{ch}: {volt}V, {curr}A")
                dp.set_channel(ch, volt, curr)
            except Exception as e:
                self.log(f"Error setting DP: {e}")
        
        self.log("Power Configuration Completed.")

    def start_linearity_test(self):
        try:
            start_v = float(self.txt_start.text())
            step_v = float(self.txt_step.text())
            points = int(self.txt_points.text())
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter valid numeric values.")
            return
            
        source_type = "DAC" if self.rb_dac.isChecked() else "DG"
        
        # Use Aliases instead of raw addresses
        # Note: combo_dac_sel_lin is now used for Linearity Tab
        dac_alias = self.combo_dac_sel_lin.currentText()
        dac_ch = self.txt_dac_ch.text()

        dg_alias = self.combo_dg_sel.currentText()
        
        active_ch = dac_ch if source_type == "DAC" else self.txt_dg_ch.text()
        
        dm_alias = self.combo_dm_sel.currentText()
        
        self.lin_worker = LinearityWorker(self.inst_mgr, source_type, start_v, step_v, points, dac_alias, active_ch, dm_alias, dg_alias)
        self.lin_worker.log_signal.connect(self.log)
        self.lin_worker.progress_signal.connect(self.progress_bar.setValue)
        self.lin_worker.result_signal.connect(self.update_plot)
        self.lin_worker.finished_signal.connect(lambda: self.log("Linearity Test Completed."))
        self.lin_worker.start()

    def update_plot(self, x, y, metrics):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(x, y, 'b.-', label='Measured')
        
        gain = metrics['gain']
        offset = metrics['offset']
        y_fit = np.array(x) * gain + offset
        ax.plot(x, y_fit, 'r--', label=f'Fit (G={gain:.4f}, Off={offset:.4f})')
        
        ax.set_title("DC Linearity")
        ax.set_xlabel("Input (V)")
        ax.set_ylabel("Measured (V)")
        ax.legend()
        ax.grid(True)
        
        self.canvas.draw()
        
        self.log(f"Metrics: Gain={gain:.6f}, Offset={offset:.6f}")
        self.log(f"Max INL: {np.max(np.abs(metrics['inl'])):.4f} LSB")
        self.log(f"Max DNL: {np.max(np.abs(metrics['dnl'])):.4f} LSB")

        # Save Plot
        import os
        os.makedirs("image", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        img_filename = f"image/dc_linearity_result_{timestamp}.png"
        try:
            self.figure.savefig(img_filename)
            self.log(f"Plot saved to {img_filename}")
        except Exception as e:
            self.log(f"Error saving plot: {e}")
