#!/usr/bin/env python3
"""
Simple GUI test to verify PySide6 window display.
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

class SimpleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Test Window")
        self.setGeometry(200, 200, 400, 300)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        layout = QVBoxLayout(central_widget)
        
        # Label
        label = QLabel("✅ GUI is working!\n\nIf you see this, PySide6 is properly installed.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2e7d32;
                padding: 20px;
                border: 2px solid #4caf50;
                border-radius: 10px;
                background-color: #e8f5e8;
            }
        """)
        layout.addWidget(label)
        
        # Force window to front
        self.raise_()
        self.activateWindow()
        self.show()

def main():
    app = QApplication(sys.argv)
    
    window = SimpleWindow()
    
    print("✅ Simple test window created")
    print("Window position:", window.x(), window.y())
    print("Window size:", window.width(), window.height())
    print("\n🔍 If you don't see the window:")
    print("1. Check your dock (bottom of screen)")
    print("2. Try Cmd+Tab to switch between apps")
    print("3. Check if window is behind other windows")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())