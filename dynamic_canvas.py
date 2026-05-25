import sys
import os
import json
import cv2
import time
import math
import datetime
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QScrollArea)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPointF
from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPen

UI_STATE_FILE = "data/ui_state.json"
QUEUE_FILE = "data/heartbeat_queue.json"

class VideoCaptureThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)

    def __init__(self, device_path, width, height):
        super().__init__()
        self.device_path = device_path
        self.width = width
        self.height = height
        self._run_flag = True

    def run(self):
        # Handle /dev/video0 -> 0 for cv2
        dev_id = 0 if self.device_path == "/dev/video0" else self.device_path
        cap = cv2.VideoCapture(dev_id)
        if not cap.isOpened():
            print(f"Warning: Cannot open video device {self.device_path}")
            return

        while self._run_flag:
            ret, cv_img = cap.read()
            if ret:
                cv_img = cv2.resize(cv_img, (self.width, self.height))
                qt_img = self.convert_cv_qt(cv_img)
                self.change_pixmap_signal.emit(qt_img)
            self.msleep(30) # ~30fps
        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()

    def convert_cv_qt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return convert_to_Qt_format

class DynamicCanvas(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Apollo DRADIS Console")
        self.resize(1280, 800)
        # Deep black background for the tactical feel
        self.setStyleSheet("background-color: #020202; color: #FFB000; font-family: 'Courier New', Courier, monospace;")
        
        self.central_widget = QWidget()
        # Make the central widget transparent so the main window paintEvent (radar) shows through
        self.central_widget.setStyleSheet("background: transparent;")
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(30, 30, 30, 30) # Leave room for the grid
        
        self.current_state_mtime = 0
        self.video_threads = []
        
        # State logic for radar sweep
        self.sweep_angle = 0.0
        
        # Fast timer for smooth 60fps radar sweep animation
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_sweep)
        self.anim_timer.start(16)
        
        # Poll for UI updates from Zoey
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_ui_state)
        self.timer.start(500) # Check every 500ms

        self.render_placeholder()

    def update_sweep(self):
        self.sweep_angle = (self.sweep_angle + 1.5) % 360
        self.update() # Trigger paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        cx, cy = rect.width() / 2, rect.height() / 2
        radius = min(cx, cy) - 20
        
        # 1. Draw Grid Lines (Amber Phosphor look)
        grid_pen = QPen(QColor(255, 176, 0, 40)) # Faint Amber
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        
        # Concentric circles
        for r in range(50, int(radius), 50):
            painter.drawEllipse(QPointF(cx, cy), r, r)
            
        # Crosshairs
        painter.drawLine(int(cx), 0, int(cx), rect.height())
        painter.drawLine(0, int(cy), rect.width(), int(cy))
        
        # 2. Draw Radar Sweep
        sweep_pen = QPen(QColor(255, 176, 0, 150)) # Bright Amber
        sweep_pen.setWidth(3)
        painter.setPen(sweep_pen)
        
        rad_angle = math.radians(self.sweep_angle)
        end_x = cx + radius * math.sin(rad_angle)
        end_y = cy - radius * math.cos(rad_angle)
        painter.drawLine(QPointF(cx, cy), QPointF(end_x, end_y))
        
        # Draw gradient trail for the sweep
        for i in range(1, 20):
            trail_angle = math.radians((self.sweep_angle - i) % 360)
            trail_x = cx + radius * math.sin(trail_angle)
            trail_y = cy - radius * math.cos(trail_angle)
            alpha = max(0, 150 - (i * 7))
            trail_pen = QPen(QColor(255, 176, 0, alpha))
            trail_pen.setWidth(2)
            painter.setPen(trail_pen)
            painter.drawLine(QPointF(cx, cy), QPointF(trail_x, trail_y))

    def render_placeholder(self):
        self.clear_layout(self.main_layout)
        label = QLabel("Awaiting Apollo UI Payload...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Monospace", 18))
        self.main_layout.addWidget(label)

    def check_ui_state(self):
        if not os.path.exists(UI_STATE_FILE):
            return
            
        mtime = os.path.getmtime(UI_STATE_FILE)
        if mtime > self.current_state_mtime:
            self.current_state_mtime = mtime
            try:
                with open(UI_STATE_FILE, 'r') as f:
                    payload = json.load(f)
                self.render_payload(payload)
            except Exception as e:
                print(f"Canvas Error parsing JSON: {e}")

    def clear_layout(self, layout):
        # Stop existing video threads
        for t in self.video_threads:
            t.stop()
        self.video_threads.clear()

        if layout is not None:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
                elif child.layout():
                    self.clear_layout(child.layout())

    def render_payload(self, payload):
        self.clear_layout(self.main_layout)
        
        # Intercept Ask User Prompts
        if payload.get("type") == "ask_user_prompt":
            self.render_ask_user(payload)
            return

        self.actions = payload.get("actions", {})
        root_node = payload.get("root", {})
        
        if root_node:
            widget = self.build_widget(root_node)
            if widget:
                self.main_layout.addWidget(widget)
        else:
            self.render_placeholder()

    def render_ask_user(self, payload):
        questions = payload.get("questions", [])
        self.ask_user_answers = {}
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        
        header = QLabel("APOLLO REQUIRES INPUT")
        header.setFont(QFont("Monospace", 18, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        layout.addSpacing(20)
        
        for q in questions:
            q_text = q.get("question", "")
            q_header = q.get("header", "")
            
            lbl = QLabel(f"[{q_header}] {q_text}")
            lbl.setFont(QFont("Monospace", 14, QFont.Weight.Bold))
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            
            q_type = q.get("type", "choice")
            if q_type == "choice":
                for opt in q.get("options", []):
                    btn_text = f"{opt.get('label', '')} - {opt.get('description', '')}"
                    btn = QPushButton(btn_text)
                    btn.setFixedHeight(50)
                    btn.setStyleSheet("background-color: #2D2D2D; border: 1px solid #FFB000; border-radius: 5px; color: #FFB000; text-align: left; padding-left: 15px; font-size: 14px;")
                    btn.clicked.connect(lambda _, q_txt=q_text, ans=opt.get("label", ""): self.submit_ask_user(q_txt, ans))
                    layout.addWidget(btn)
            elif q_type == "text":
                inp = QLineEdit()
                inp.setStyleSheet("background-color: #111; color: #FFB000; border: 1px solid #FFB000; padding: 10px; font-size: 14px;")
                inp.setPlaceholderText(q.get("placeholder", "Type your answer and press Enter..."))
                inp.returnPressed.connect(lambda i=inp, q_txt=q_text: self.submit_ask_user(q_txt, i.text()))
                layout.addWidget(inp)
            elif q_type == "yesno":
                hbox = QHBoxLayout()
                btn_yes = QPushButton("Yes")
                btn_no = QPushButton("No")
                for b, ans in [(btn_yes, "Yes"), (btn_no, "No")]:
                    b.setFixedHeight(50)
                    b.setStyleSheet("background-color: #2D2D2D; border: 1px solid #FFB000; border-radius: 5px; color: #FFB000; font-size: 14px; font-weight: bold;")
                    b.clicked.connect(lambda _, q_txt=q_text, a=ans: self.submit_ask_user(q_txt, a))
                    hbox.addWidget(b)
                layout.addLayout(hbox)
                
            layout.addSpacing(30)
            
        layout.addStretch()
        scroll.setWidget(container)
        self.main_layout.addWidget(scroll)

    def submit_ask_user(self, question_text, answer):
        self.ask_user_answers[question_text] = answer
        
        # Write to user_response.json
        response_file = "data/user_response.json"
        try:
            with open(response_file, 'w') as f:
                json.dump(self.ask_user_answers, f, indent=2)
            print(f"[CANVAS] Submitted answer: {answer}")
            
            # Show waiting label
            self.clear_layout(self.main_layout)
            lbl = QLabel("Answer submitted. Resuming Apollo...")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(QFont("Monospace", 18))
            self.main_layout.addWidget(lbl)
            
        except Exception as e:
            print(f"[CANVAS] Error writing response: {e}")

    def build_widget(self, node):
        node_type = node.get("type")
        
        if node_type == "VBox":
            container = QWidget()
            layout = QVBoxLayout(container)
            for child in node.get("children", []):
                w = self.build_widget(child)
                if w: layout.addWidget(w)
            return container
            
        elif node_type == "HBox":
            container = QWidget()
            layout = QHBoxLayout(container)
            for child in node.get("children", []):
                w = self.build_widget(child)
                if w: layout.addWidget(w)
            return container
            
        elif node_type == "Label":
            label = QLabel(node.get("text", ""))
            # Basic style parsing
            style = node.get("style", {})
            if "font" in style:
                label.setFont(QFont("Monospace", 14, QFont.Weight.Bold if "bold" in style["font"] else QFont.Weight.Normal))
            return label
            
        elif node_type == "Button":
            btn = QPushButton(node.get("text", ""))
            btn.setFixedHeight(50)
            btn.setStyleSheet("background-color: #2D2D2D; border: 1px solid #555; border-radius: 5px; font-weight: bold;")
            action_key = node.get("action")
            if action_key:
                btn.clicked.connect(lambda _, ak=action_key: self.trigger_action(ak))
            return btn
            
        elif node_type == "VideoFeed":
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background-color: #000000;")
            res = node.get("resolution", {"width": 640, "height": 480})
            label.setMinimumSize(res["width"], res["height"])
            
            thread = VideoCaptureThread(node.get("device", "/dev/video0"), res["width"], res["height"])
            thread.change_pixmap_signal.connect(label.setPixmap)
            thread.start()
            self.video_threads.append(thread)
            return label

        return None

    def trigger_action(self, action_key):
        action_def = self.actions.get(action_key)
        if not action_def: return
        
        print(f"[CANVAS] Action Triggered: {action_key} -> {action_def}")

        if action_def.get("type") == "execute_shell":
            command = action_def.get("command")
            if command:
                print(f"[CANVAS] Executing shell command: {command}")
                # Run the command asynchronously so we don't freeze the GUI
                subprocess.Popen(command, shell=True)
            return
        
        # Inject the UI action back into the heartbeat queue for Zoey to process
        task = {
            "id": f"UI-{int(time.time() * 1000)}",
            "timestamp": time.time(),
            "source": "dynamic_canvas",
            "urgency": "normal",
            "description": f"User clicked UI button mapped to action: {action_def.get('type')}",
            "context": action_def,
            "status": "pending"
        }
        
        try:
            tasks = []
            if os.path.exists(QUEUE_FILE):
                with open(QUEUE_FILE, 'r') as f:
                    tasks = json.load(f)
            tasks.append(task)
            with open(QUEUE_FILE, 'w') as f:
                json.dump(tasks, f, indent=2)
        except Exception as e:
            print(f"Failed to push action to queue: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DynamicCanvas()
    window.show()
    sys.exit(app.exec())
