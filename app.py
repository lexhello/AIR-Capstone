import cv2
import mediapipe as mp
import threading
import time
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget
import simpleaudio as sa

# --- MediaPipe setup ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)

class HandApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaPipe Hand Detection App")
        self.setGeometry(300, 200, 700, 600)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(720, 640)
        
        self.button = QPushButton("Start Camera")
        self.button.clicked.connect(self.toggle_camera)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.cooldown = False
        self.cooldown_duration = 1.0
        self.last_detection_time = 0

        self.sound = sa.WaveObject.from_wave_file("beep.wav")  # <-- place a beep.wav file in same folder

    def toggle_camera(self):
        if self.timer.isActive():
            self.timer.stop()
            self.cap.release()
            self.button.setText("Start Camera")
        else:
            self.cap = cv2.VideoCapture(0)
            self.timer.start(30)
            self.button.setText("Stop Camera")

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)

        left_detected = False
        if results.multi_hand_landmarks:
            for idx, handedness in enumerate(results.multi_handedness):
                mp_drawing.draw_landmarks(frame, results.multi_hand_landmarks[idx], mp_hands.HAND_CONNECTIONS)
                if handedness.classification[0].label == "Left":
                    left_detected = True

        if left_detected and not self.cooldown:
            self.sound.play()
            self.cooldown = True
            self.last_detection_time = time.time()
            threading.Timer(self.cooldown_duration, lambda: setattr(self, 'cooldown', False)).start()

        text = "LEFT HAND DETECTED!" if left_detected else "No left hand detected"
        color = (0, 255, 0) if left_detected else (0, 0, 255)
        cv2.putText(frame, text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
        
        # --- Preserve aspect ratio and fit into QLabel ---
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        label_w, label_h = self.video_label.width(), self.video_label.height()

        # Compute scaling factor to fit the frame in the label
        scale = min(label_w / w, label_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized_frame = cv2.resize(frame_rgb, (new_w, new_h))

        # Create black background and center the resized frame
        canvas = np.zeros((label_h, label_w, 3), dtype=np.uint8)
        x_offset = (label_w - new_w) // 2
        y_offset = (label_h - new_h) // 2
        canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized_frame

        # Convert to QImage
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
