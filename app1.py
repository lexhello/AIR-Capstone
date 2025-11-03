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
import pygame
from PyQt5.QtWidgets import QComboBox

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
        self.mode_dropdown = QComboBox()
        self.mode_dropdown.addItems(["normal", "lisa"])
        self.mode_dropdown.currentIndexChanged.connect(self.on_dropdown_change)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.button)
        layout.addWidget(self.mode_dropdown)

        self.setLayout(layout)

        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.active_notes = set()
        self.currently_playing = set()

        self.cooldown = False
        self.cooldown_duration = 1.0
        self.last_detection_time = 0
        try:
            self.sound = sa.WaveObject.from_wave_file("beep.wav")
        except Exception:
            self.sound = None
            print("No beep.wav found – sound disabled.")
        pygame.mixer.init()
        try:
            if self.mode_dropdown.currentText() == "normal":
                self.c4 = pygame.mixer.Sound("static/audio/c4.mp3")
                self.d4 = pygame.mixer.Sound("static/audio/d4.mp3")
                self.e4 = pygame.mixer.Sound("static/audio/e4.mp3")
                self.f4 = pygame.mixer.Sound("static/audio/f4.mp3")
                self.g4 = pygame.mixer.Sound("static/audio/g4.mp3")
                self.a4 = pygame.mixer.Sound("static/audio/a4.mp3")
                self.b4 = pygame.mixer.Sound("static/audio/b4.mp3")
                self.c5 = pygame.mixer.Sound("static/audio/c5.mp3")
                print("Audio files loaded successfully.")
            elif self.mode_dropdown.currentText() == "lisa":
                self.c4 = pygame.mixer.Sound("static/audio/lisa-a3.mp3")
                self.d4 = pygame.mixer.Sound("static/audio/lisa-b3.mp3")
                self.e4 = pygame.mixer.Sound("static/audio/lisa-c4.mp3")
                self.f4 = pygame.mixer.Sound("static/audio/lisa-d4.mp3")
                self.g4 = pygame.mixer.Sound("static/audio/lisa-e4.mp3")
                self.a4 = pygame.mixer.Sound("static/audio/lisa-f4.mp3")
                self.b4 = pygame.mixer.Sound("static/audio/lisa-g4.mp3")
                self.c5 = pygame.mixer.Sound("static/audio/lisa-a4.mp3")    
                print("Lisa audio files loaded successfully.")
        except Exception as e:
            print("Error loading audio:", e)

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
    
    def on_dropdown_change(self, index):
        selected_mode = self.mode_dropdown.currentText()
        print(f"Mode changed to: {selected_mode}")
        try:
            if selected_mode == "normal":
                self.c4 = pygame.mixer.Sound("static/audio/c4.mp3")
                self.d4 = pygame.mixer.Sound("static/audio/d4.mp3")
                self.e4 = pygame.mixer.Sound("static/audio/e4.mp3")
                self.f4 = pygame.mixer.Sound("static/audio/f4.mp3")
                self.g4 = pygame.mixer.Sound("static/audio/g4.mp3")
                self.a4 = pygame.mixer.Sound("static/audio/a4.mp3")
                self.b4 = pygame.mixer.Sound("static/audio/b4.mp3")
                self.c5 = pygame.mixer.Sound("static/audio/c5.mp3")
                print("Switched to normal audio files.")
            elif selected_mode == "lisa":
                self.c4 = pygame.mixer.Sound("static/audio/lisa-a3.mp3")
                self.d4 = pygame.mixer.Sound("static/audio/lisa-b3.mp3")
                self.e4 = pygame.mixer.Sound("static/audio/lisa-c4.mp3")
                self.f4 = pygame.mixer.Sound("static/audio/lisa-d4.mp3")
                self.g4 = pygame.mixer.Sound("static/audio/lisa-e4.mp3")
                self.a4 = pygame.mixer.Sound("static/audio/lisa-f4.mp3")
                self.b4 = pygame.mixer.Sound("static/audio/lisa-g4.mp3")
                self.c5 = pygame.mixer.Sound("static/audio/lisa-a4.mp3")
                print("Switched to lisa audio files.")
        except Exception as e:
            print("Error loading audio on mode change:", e)

    def distance(self, a, b):
        """Helper function to compute Euclidean distance between two 2D points."""
        return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

    # Return the angle (in degrees) formed by points a-b-c at b.
    def finger_angle(self, a, b, c):
        ba = (a[0] - b[0], a[1] - b[1])
        bc = (c[0] - b[0], c[1] - b[1])
        dot = ba[0]*bc[0] + ba[1]*bc[1]
        mag = math.sqrt((ba[0]**2 + ba[1]**2) * (bc[0]**2 + bc[1]**2))
        if mag == 0:
            return 180
        cos_angle = max(min(dot / mag, 1), -1)
        return math.degrees(math.acos(cos_angle))

    def detect_fingers(self, landmarks):
        coords = [(lm.x, lm.y, lm.z) for lm in landmarks.landmark]
        finger_states = {}

        # Thumb (use x-axis since it's sideways)
        thumb_tip_x, thumb_ip_x = coords[FINGER_TIPS[0]][0], coords[FINGER_PIPS[0]][0]
        finger_states["Thumb"] = "Bent" if thumb_tip_x < thumb_ip_x else "Straight"

        # Other fingers – use joint angles
        for i, name in enumerate(FINGER_NAMES[1:], start=1):
            mcp = coords[FINGER_BASES[i]]  # base
            pip = coords[FINGER_PIPS[i]]   # middle
            tip = coords[FINGER_TIPS[i]]   # tip

            angle = self.finger_angle(mcp, pip, tip)
            # smaller angle = more bent
            if angle < 160:  # tweak: 150–170
                finger_states[name] = "Bent"
            else:
                finger_states[name] = "Straight"

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

                # if states.get("Index") == "Bent":
                #     self.sound.play()

                pattern1 = states.get("Thumb") == "Bent" and states.get("Index") == "Straight" and states.get("Middle") == "Bent" and states.get("Ring") == "Bent" and states.get("Pinky") == "Bent"
                pattern2 = states.get("Thumb") == "Bent" and states.get("Index") == "Straight" and states.get("Middle") == "Straight" and states.get("Ring") == "Bent" and states.get("Pinky") == "Bent"
                pattern3 = states.get("Thumb") == "Bent" and states.get("Index") == "Straight" and states.get("Middle") == "Straight" and states.get("Ring") == "Straight" and states.get("Pinky") == "Bent"
                pattern4 = states.get("Thumb") == "Bent" and states.get("Index") == "Straight" and states.get("Middle") == "Straight" and states.get("Ring") == "Straight" and states.get("Pinky") == "Straight"
                pattern5 = states.get("Thumb") == "Straight" and states.get("Index") == "Straight" and states.get("Middle") == "Straight" and states.get("Ring") == "Straight" and states.get("Pinky") == "Straight"
                pattern6 = states.get("Thumb") == "Straight" and states.get("Index") == "Bent" and states.get("Middle") == "Bent" and states.get("Ring") == "Bent" and states.get("Pinky") == "Bent"

                # hand is position 1
                if pattern1:
                    self.currently_playing.add("c4")
                    self.currently_playing.add("e4")
                    self.currently_playing.add("g4")
                # hand in position 2
                elif pattern2:
                    self.currently_playing.add("d4")
                    self.currently_playing.add("f4")
                    self.currently_playing.add("a4")
                # hand in position 3
                elif pattern3:
                    self.currently_playing.add("e4")
                    self.currently_playing.add("g4")
                    self.currently_playing.add("b4")
                # hand in position 4
                elif pattern4:
                    self.currently_playing.add("f4")
                    self.currently_playing.add("a4")
                    self.currently_playing.add("c5")
                # hand in position 5
                elif pattern5:
                    self.currently_playing.add("g4")
                    self.currently_playing.add("b4")
                    self.currently_playing.add("d5")
                # hand is position 6
                elif pattern6:
                    self.currently_playing.add("a4")
                    self.currently_playing.add("c5")

                to_stop = self.active_notes - self.currently_playing
                to_start = self.currently_playing - self.active_notes

                for note in to_stop:
                    if note == "c4":
                        self.c4.stop()
                    elif note == "d4":
                        self.d4.stop()
                    elif note == "e4":
                        self.e4.stop()
                    elif note == "f4":
                        self.f4.stop()
                    elif note == "g4":
                        self.g4.stop()
                    elif note == "a4":
                        self.a4.stop()
                    elif note == "b4":
                        self.b4.stop()
                    elif note == "c5":
                        self.c5.stop()
                # Play active notes
                for note in to_start:
                    if note == "c4":
                        self.c4.play()
                    elif note == "d4":
                        self.d4.play()
                    elif note == "e4":
                        self.e4.play()
                    elif note == "f4":
                        self.f4.play()
                    elif note == "g4":
                        self.g4.play()
                    elif note == "a4":
                        self.a4.play()
                    elif note == "b4":
                        self.b4.play()
                    elif note == "c5":
                        self.c5.play()
                self.active_notes = self.currently_playing.copy()
                self.currently_playing.clear()
                    
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
