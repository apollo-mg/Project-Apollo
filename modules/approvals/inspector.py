import sys
import os
import json
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                             QLabel, QTextEdit, QPushButton, QSplitter)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

class LogicInspector(QDialog):
    def __init__(self, action_name, params, thought_trace="", parent=None):
        super().__init__(parent)
        self.action_name = action_name
        self.params = params
        self.thought_trace = thought_trace
        self.result = "denied"
        self.edited_params = params
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"Apollo Logic Inspector - {self.action_name}")
        self.resize(1000, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout()
        
        # Header Layout (Title + Webcam Status)
        header_layout = QHBoxLayout()
        
        header = QLabel(f"ACTION INTERCEPTED: {self.action_name}")
        header.setFont(QFont("Monospace", 14, QFont.Weight.Bold))
        header_layout.addWidget(header)
        
        # Spacer to push status to the right
        header_layout.addStretch()
        
        # Webcam Status Indicator (Logitech C920)
        # Quick check for video devices (assuming /dev/video0 is the webcam on Linux)
        cam_detected = os.path.exists('/dev/video0')
        status_color = "#00FF00" if cam_detected else "#FF0000"
        status_text = "Logitech C920: ONLINE" if cam_detected else "Logitech C920: OFFLINE"
        
        self.cam_indicator = QLabel()
        self.cam_indicator.setFixedSize(16, 16)
        self.cam_indicator.setStyleSheet(f"background-color: {status_color}; border-radius: 8px;")
        
        cam_label = QLabel(status_text)
        cam_label.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        
        header_layout.addWidget(self.cam_indicator)
        header_layout.addWidget(cam_label)
        
        layout.addLayout(header_layout)

        # Splitter for Thinking vs Code
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Thinking Trace Pane
        thinking_layout = QVBoxLayout()
        thinking_layout.addWidget(QLabel("MODEL THINKING TRACE:"))
        self.thinking_edit = QTextEdit()
        self.thinking_edit.setReadOnly(True)
        self.thinking_edit.setPlainText(self.thought_trace or "No thought trace provided.")
        self.thinking_edit.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        self.thinking_edit.setFont(QFont("Monospace", 10))
        thinking_layout.addWidget(self.thinking_edit)
        
        thinking_widget = QDialog()
        thinking_widget.setLayout(thinking_layout)
        splitter.addWidget(thinking_widget)

        # Proposed Parameters Pane
        params_layout = QVBoxLayout()
        params_layout.addWidget(QLabel("PROPOSED PARAMETERS (EDITABLE):"))
        self.params_edit = QTextEdit()
        self.params_edit.setPlainText(self.params)
        self.params_edit.setStyleSheet("background-color: #1e1e1e; color: #9cdcfe; border: 1px solid #454545;")
        self.params_edit.setFont(QFont("Monospace", 11))
        params_layout.addWidget(self.params_edit)
        
        params_widget = QDialog()
        params_widget.setLayout(params_layout)
        splitter.addWidget(params_widget)
        
        layout.addWidget(splitter)

        # Control Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_abort = QPushButton("🛑 ABORT")
        self.btn_abort.setFixedHeight(40)
        self.btn_abort.setStyleSheet("background-color: #8b0000; color: white; font-weight: bold;")
        self.btn_abort.clicked.connect(self.on_abort)
        btn_layout.addWidget(self.btn_abort)

        self.btn_approve = QPushButton("✅ APPROVE")
        self.btn_approve.setFixedHeight(40)
        self.btn_approve.setStyleSheet("background-color: #006400; color: white; font-weight: bold;")
        self.btn_approve.clicked.connect(self.on_approve)
        btn_layout.addWidget(self.btn_approve)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def on_approve(self):
        self.result = "approved"
        self.edited_params = self.params_edit.toPlainText()
        self.accept()

    def on_abort(self):
        self.result = "denied"
        self.reject()

def launch_inspector(action_name, params, thought_trace=""):
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    inspector = LogicInspector(action_name, params, thought_trace)
    inspector.exec()
    return inspector.result, inspector.edited_params

if __name__ == "__main__":
    # Test Launch
    res, edited = launch_inspector("run_shell", "ls -la /root", "I want to see if I have root access.")
    print(f"Result: {res}, Params: {edited}")
