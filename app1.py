import cv2
import mediapipe as mp
import threading
import time
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget
import simpleaudio as sa
import math

# --- MediaPipe setup ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)

# --- Finger landmark IDs ---
FINGER_TIPS = [4, 8, 12, 16, 20]
FINGER_PIPS = [3, 6, 10, 14, 18]
FINGER_BASES = [2, 5, 9, 13, 17]
FINGER_NAMES = ["Thumb", "Index", "Middle", "Ring", "Pinky"]

class HandApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaPipe Hand Detection App")
        self.setGeometry(300, 200, 700, 700)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(640, 480)

        self.status_label = QLabel("Finger Status: None")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; color: white; background-color: #333; padding: 6px;")

        self.button = QPushButton("Start Camera")
        self.button.clicked.connect(self.toggle_camera)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.cooldown = False
        self.cooldown_duration = 1.0
        self.last_detection_time = 0

        try:
            self.sound = sa.WaveObject.from_wave_file("beep.wav")
        except Exception:
            self.sound = None
            print("No beep.wav found – sound disabled.")

    def toggle_camera(self):
        if self.timer.isActive():
            self.timer.stop()
            if self.cap:
                self.cap.release()
            self.button.setText("Start Camera")
        else:
            self.cap = cv2.VideoCapture(0)
            self.timer.start(30)
            self.button.setText("Stop Camera")

    def distance(self, a, b):
        """Helper function to compute Euclidean distance between two 2D points."""
        return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

    def detect_fingers(self, landmarks):
        """Return dict with finger name -> bent/straight"""
        finger_states = {}

        # Extract landmarks into simpler lists
        coords = [(lm.x, lm.y) for lm in landmarks.landmark]

        # Thumb uses x axis comparison (sideways)
        thumb_tip_x, thumb_ip_x = coords[FINGER_TIPS[0]][0], coords[FINGER_PIPS[0]][0]
        finger_states["Thumb"] = "Bent" if thumb_tip_x < thumb_ip_x else "Straight"

        # Other fingers use y axis comparison (vertical)
        for i in range(1, 5):
            if i in [2, 3, 4]:
                # --- Middle Finger (ratio comparison) ---
                base = coords[FINGER_BASES[i]]   # MCP
                mid = coords[FINGER_PIPS[i]]   # PIP
                tip = coords[FINGER_TIPS[i]]   # TIP
                base_to_mid = self.distance(base, mid)
                mid_to_tip = self.distance(mid, tip)
                ratio = mid_to_tip / base_to_mid if base_to_mid != 0 else 0

                if ratio < 0.6:  # Threshold can be tuned between 0.6–0.8
                    # finger_states["Middle"] = f"Bent ({ratio:.2f})"
                    finger_states[FINGER_NAMES[i]] = "Bent"
                else:
                    # finger_states["Middle"] = f"Straight ({ratio:.2f})"
                    finger_states[FINGER_NAMES[i]] = "Straight"
            else:
                tip_y, pip_y = coords[FINGER_TIPS[i]][1], coords[FINGER_PIPS[i]][1]
                finger_states[FINGER_NAMES[i]] = "Bent" if tip_y > pip_y else "Straight"

        return finger_states

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)

        finger_text = "No hand detected"

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # Detect fingers
                states = self.detect_fingers(hand_landmarks)
                finger_text = " | ".join([f"{f}: {s}" for f, s in states.items()])

                if states.get("Index") == "Bent":
                    self.sound.play()
                    
                # # Play sound on left-hand detection (optional)
                # if not self.cooldown:
                #     if self.sound:
                #         self.sound.play()
                #     self.cooldown = True
                #     threading.Timer(self.cooldown_duration, lambda: setattr(self, 'cooldown', False)).start()

        # Update the on-screen label
        self.status_label.setText(f"Finger Status: {finger_text}")

        # Draw title overlay
        cv2.putText(frame, "MediaPipe Finger Tracking", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

        # --- Preserve aspect ratio ---
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        label_w, label_h = self.video_label.width(), self.video_label.height()
        scale = min(label_w / w, label_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized_frame = cv2.resize(frame_rgb, (new_w, new_h))
        canvas = np.zeros((label_h, label_w, 3), dtype=np.uint8)
        x_offset = (label_w - new_w) // 2
        y_offset = (label_h - new_h) // 2
        canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized_frame

        qt_image = QImage(canvas.data, label_w, label_h, 3 * label_w, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qt_image))

    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication([])
    win = HandApp()
    win.show()
    app.exec_()
