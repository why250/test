import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

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
