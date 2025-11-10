import cv2
import mediapipe as mp
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget, QComboBox
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from bleak import BleakScanner, BleakClient
import simpleaudio as sa
import math
import pygame
import sys
from qasync import QEventLoop
from receiver import BLEReader
import asyncio

# --- MediaPipe setup ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)

# --- Finger landmark IDs ---
FINGER_TIPS = [4, 8, 12, 16, 20]
FINGER_PIPS = [3, 6, 10, 14, 18]
FINGER_BASES = [2, 5, 9, 13, 17]
FINGER_NAMES = ["Thumb", "Index", "Middle", "Ring", "Pinky"]

DELAYS = [0.040, 0.030, 0.020, 0.010]

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

class HandApp(QWidget):
    
    ble_notification_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.ble_notification_signal.connect(self.handle_ble_notification)
        self.setWindowTitle("MediaPipe Hand Detection App")
        self.setGeometry(300, 200, 700, 700)

        # UI elements
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(640, 480)

        self.status_label = QLabel("Finger Status: None")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; color: white; background-color: #333; padding: 6px;")

        self.Camera_button = QPushButton("Start Camera")
        self.Camera_button.clicked.connect(self.toggle_camera)
        
        self.Overlap_sounds_button = QPushButton("Overlap Sounds")
        self.Overlap_sounds_button.clicked.connect(self.overlap_sounds)

        self.mode_dropdown = QComboBox()
        self.mode_dropdown.addItems(["normal", "lisa"])
        self.mode_dropdown.currentIndexChanged.connect(self.on_dropdown_change)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.Camera_button)
        layout.addWidget(self.Overlap_sounds_button)
        layout.addWidget(self.mode_dropdown)
        self.setLayout(layout)

        # State
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: asyncio.create_task(self.update_frame()))
        self.active_notes = set()
        self.selected_notes = set()
        self.currently_playing = set()
        self.new_strum_flag = [False]  # <- mutable boolean
        self.sound_overlapping = False

        # Audio
        try:
            self.sound = sa.WaveObject.from_wave_file("beep.wav")
        except Exception:
            self.sound = None
            print("No beep.wav found – sound disabled.")
        pygame.mixer.init()
        self.load_audio_files(self.mode_dropdown.currentText())

        # BLE
        self.ble = None

    def handle_ble_notification(self, decoded: str):
        """Called in Qt event loop - safe to update UI and flags"""
        print(f"BLE Notification: {decoded}", file=sys.stderr, flush=True)
        self.status_label.setText(f"BLE: {decoded}")
        self.new_strum_flag[0] = True
        
    
    def load_audio_files(self, mode):
        try:
            if mode == "normal":
                self.c4 = pygame.mixer.Sound("static/audio/c4.mp3")
                self.d4 = pygame.mixer.Sound("static/audio/d4.mp3")
                self.e4 = pygame.mixer.Sound("static/audio/e4.mp3")
                self.f4 = pygame.mixer.Sound("static/audio/f4.mp3")
                self.g4 = pygame.mixer.Sound("static/audio/g4.mp3")
                self.a4 = pygame.mixer.Sound("static/audio/a4.mp3")
                self.b4 = pygame.mixer.Sound("static/audio/b4.mp3")
                self.c5 = pygame.mixer.Sound("static/audio/c5.mp3")
            elif mode == "lisa":
                self.c4 = pygame.mixer.Sound("static/audio/lisa-a3.mp3")
                self.d4 = pygame.mixer.Sound("static/audio/lisa-b3.mp3")
                self.e4 = pygame.mixer.Sound("static/audio/lisa-c4.mp3")
                self.f4 = pygame.mixer.Sound("static/audio/lisa-d4.mp3")
                self.g4 = pygame.mixer.Sound("static/audio/lisa-e4.mp3")
                self.a4 = pygame.mixer.Sound("static/audio/lisa-f4.mp3")
                self.b4 = pygame.mixer.Sound("static/audio/lisa-g4.mp3")
                self.c5 = pygame.mixer.Sound("static/audio/lisa-a4.mp3")
            print(f"{mode} audio files loaded successfully.")
        except Exception as e:
            print("Error loading audio:", e)

    async def init_ble(self):
        
        print("🔍 Scanning for BLE devices...")
        devices = await BleakScanner.discover(timeout=6.0)

        target = None
        for d in devices:
            print(f"- {d.name or 'Unknown'} ({d.address})")
            if d.name and "XIAO_ESP32S3" in d.name:
                target = d
                break

        if not target:
            print("Could not find XIAO_ESP32S3.")
            self.Client = None
            return

        print(f"\nFound device: {target.name} [{target.address}]")
        print("Connecting...")

        self.client = BleakClient(target.address)
        await self.client.connect()

        if not self.client.is_connected:
            print("Failed to connect to ESP32 BLE Server")
            self.client = None
            return

        print("CONNECTED !!  to ESP32 BLE Server")

        await self.client.start_notify(CHARACTERISTIC_UUID, self._notification_handler)
        print("Subscribed to notifications.")
        
    def _notification_handler(self, sender: int, data: bytearray):
        """
        Called automatically by Bleak when the characteristic notifies.
        Sets the boolean to True.
        """
        decoded = data.decode('utf-8', errors='ignore')
        print(f"Notification received from {sender}|||| {decoded}", flush=True)
        
        self.ble_notification_signal.emit(decoded)

    def toggle_camera(self):
        if self.timer.isActive():
            self.timer.stop()
            if self.cap:
                self.cap.release()
            self.Camera_button.setText("Start Camera")
        else:
            self.cap = cv2.VideoCapture(0)
            self.timer.start(30)
            self.Camera_button.setText("Stop Camera")
    
    def overlap_sounds(self):
        if not self.sound_overlapping:
            self.Overlap_sounds_button.setText("press to overlap sounds")
            self.sound_overlapping = True
        else:
            self.sound_overlapping = False
            self.Overlap_sounds_button.setText("press to stop overlapping sounds")

    def on_dropdown_change(self, index):
        selected_mode = self.mode_dropdown.currentText()
        self.load_audio_files(selected_mode)

    def distance(self, a, b):
        return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

    def finger_angle(self, a, b, c):
        ba = (a[0] - b[0], a[1] - b[1])
        bc = (c[0] - b[0], c[1] - b[1])
        dot = ba[0] * bc[0] + ba[1] * bc[1]
        mag = math.sqrt((ba[0] ** 2 + ba[1] ** 2) * (bc[0] ** 2 + bc[1] ** 2))
        if mag == 0:
            return 180
        cos_angle = max(min(dot / mag, 1), -1)
        return math.degrees(math.acos(cos_angle))

    def detect_fingers(self, landmarks):
        coords = [(lm.x, lm.y, lm.z) for lm in landmarks.landmark]
        finger_states = {}

        thumb_tip_x, thumb_ip_x = coords[FINGER_TIPS[0]][0], coords[FINGER_PIPS[0]][0]
        finger_states["Thumb"] = "Bent" if thumb_tip_x < thumb_ip_x else "Straight"

        for i, name in enumerate(FINGER_NAMES[1:], start=1):
            mcp = coords[FINGER_BASES[i]]
            pip = coords[FINGER_PIPS[i]]
            tip = coords[FINGER_TIPS[i]]
            angle = self.finger_angle(mcp, pip, tip)
            finger_states[name] = "Bent" if angle < 160 else "Straight"

        return finger_states

    async def update_frame(self):
        if self.cap is None:
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame)

        finger_text = "No hand detected"
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                states = self.detect_fingers(hand_landmarks)
                finger_text = " | ".join([f"{f}: {s}" for f, s in states.items()])

                # Patterns
                patterns = [
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Bent", "Straight", "Bent", "Bent", "Bent"], ["c4", "e4", "g4"]),
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Bent", "Straight", "Straight", "Bent", "Bent"], ["d4", "f4", "a4"]),
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Bent", "Straight", "Straight", "Straight", "Bent"], ["e4", "g4", "b4"]),
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Bent", "Bent", "Straight", "Straight", "Straight"], ["e4", "g4", "b4"]),
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Bent", "Straight", "Straight", "Straight", "Straight"], ["f4", "a4", "c5"]),
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Straight", "Straight", "Straight", "Straight", "Straight"], ["g4", "b4", "d4"]),
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Straight", "Bent", "Bent", "Bent", "Bent"], ["a4", "c5"]),
                ]
                self.currently_playing.clear()
                for fingers, states_list, notes in patterns:
                    if all(states[f] == s for f, s in zip(fingers, states_list)):
                        self.selected_notes.update(notes)
                        #self.currently_playing.update(notes)
                        break

                # Check BLE event flag
                if self.new_strum_flag[0]:
                    self.currently_playing = self.selected_notes.copy()
                    self.active_notes = self.currently_playing.copy()
                    print("reset")
                    self.new_strum_flag[0] = False  # reset flag

                # to_stop = self.active_notes - self.currently_playing
                # to_start = self.currently_playing - self.active_notes
                
                to_start = self.currently_playing
                to_stop = self.active_notes

                # Stop notes
                if not self.sound_overlapping:
                    for note in to_stop:
                        print("STOP")
                        getattr(self, note).stop()
                # Play notes
                for note in to_start:
                    getattr(self, note).play()

                self.currently_playing = set()
                self.selected_notes = set()

        self.status_label.setText(f"Finger Status: {finger_text}")

        # Render frame
        h, w, ch = frame.shape
        label_w, label_h = self.video_label.width(), self.video_label.height()
        scale = min(label_w / w, label_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized_frame = cv2.resize(frame, (new_w, new_h))
        canvas = np.zeros((label_h, label_w, 3), dtype=np.uint8)
        x_offset = (label_w - new_w) // 2
        y_offset = (label_h - new_h) // 2
        canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized_frame
        qt_image = QImage(canvas.data, label_w, label_h, 3 * label_w, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qt_image))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    win = HandApp()
    
    # Create async task for BLE init
    async def setup():
        await win.init_ble()
        print("BLE initialized and notifications handler created")
    
    async def testing():
        while True:
            win.handle_ble_notification("1")
            await asyncio.sleep(1)
        
    loop.create_task(setup())
    loop.create_task(testing())
    win.show()
    
    with loop:
        sys.exit(loop.run_forever())
