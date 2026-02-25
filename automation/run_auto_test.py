import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

import os
# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录（当前目录的上一级）
root_dir = os.path.dirname(current_dir)
# 将根目录加入sys.path
sys.path.append(root_dir)

# Ensure we are running from the root directory so relative paths (like config/visa.yaml) work
os.chdir(root_dir)

# Import the existing MainWindow
from gui.main_window import MainWindow
from automation.test_sequencer import AutoTestSequencer

if __name__ == "__main__":
    # Create Qt Application
    app = QApplication(sys.argv)
    
    # Initialize Main Window (GUI)
    window = MainWindow()
    window.show()
    
    # Initialize Automation Sequencer
    sequencer = AutoTestSequencer(window)
    
    # Start automation after a short delay to allow UI to render
    QTimer.singleShot(1000, sequencer.start)
    
    # Execute Event Loop
    sys.exit(app.exec())
