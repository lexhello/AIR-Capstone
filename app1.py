import cv2
import mediapipe as mp
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QComboBox, QSlider, QSizePolicy
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from bleak import BleakScanner, BleakClient
import simpleaudio as sa
import math
import pygame
import sys
from qasync import QEventLoop
from receiver import BLEReader
import asyncio
import time

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

        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()

        self.setGeometry(300, 200, 700, 700)
        self.setMinimumSize(700, 700)
        self.setMaximumSize(screen_width, screen_height)

        # UI elements
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        # self.video_label.setFixedSize(640, 480)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.status_label = QLabel("Finger Status: None")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; color: white; background-color: #333; padding: 6px;")

        self.song_notes_label = QLabel("")
        self.song_notes_label.setAlignment(Qt.AlignCenter)
        self.song_notes_label.setStyleSheet("font-size: 14px; color: white; background-color: #444; padding: 10px; border-radius: 5px;")
        self.song_notes_label.setWordWrap(True)
        self.song_notes_label.hide()  # Hidden by default, shown in game mode

        self.Camera_button = QPushButton("Start\nCamera")
        self.Camera_button.clicked.connect(self.toggle_camera)
        self.Camera_button.setMinimumSize(100, 100)
        self.Camera_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.Camera_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)

        self.mode_dropdown = QComboBox()
        self.mode_dropdown.addItems(["piano", "lisa", "guitar"])
        self.mode_dropdown.currentIndexChanged.connect(self.on_dropdown_change)
        self.mode_dropdown.setMinimumWidth(100)
        self.mode_dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.mode_dropdown.setStyleSheet("""
            QComboBox {
                background-color: #9C27B0;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QComboBox:hover {
                background-color: #7B1FA2;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #9C27B0;
                color: white;
                selection-background-color: #7B1FA2;
            }
        """)

        self.Overlap_sounds_button = QPushButton("Overlap OFF")
        self.Overlap_sounds_button.clicked.connect(self.overlap_sounds)
        self.Overlap_sounds_button.setMinimumSize(100, 100)
        self.Overlap_sounds_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.Overlap_sounds_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)

        self.game_mode_button = QPushButton("Game\nMode\nOFF")
        self.game_mode_button.clicked.connect(self.toggle_game_mode)
        self.game_mode_button.setMinimumSize(100, 100)
        self.game_mode_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.game_mode_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:pressed {
                background-color: #6A1B9A;
            }
        """)
        
        self.velocity_button = QPushButton("Slider\nMode")
        self.velocity_button.clicked.connect(self.toggle_velocity)
        self.velocity_button.setMinimumSize(100, 100)
        self.velocity_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.velocity_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)

        self.value_slider = QSlider(Qt.Horizontal)
        self.value_slider.setMinimum(1)
        self.value_slider.setMaximum(5)
        self.value_slider.setValue(3)  # default value
        self.value_slider.setTickPosition(QSlider.TicksBelow)
        self.value_slider.setTickInterval(1)
        self.value_slider.setMinimumWidth(100)
        self.value_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.value_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #ddd;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #FF5722;
                border: none;
                width: 20px;
                height: 20px;
                margin: -6px 0;
                border-radius: 10px;
            }
            QSlider::handle:horizontal:hover {
                background: #E64A19;
            }
            QSlider::sub-page:horizontal {
                background: #FF9800;
                border-radius: 4px;
            }
        """)

        # Label to show current value
        self.slider_label = QLabel(f"Delay: {self.value_slider.value()}")
        self.slider_label.setAlignment(Qt.AlignCenter)
        self.slider_label.setMinimumWidth(100)
        self.slider_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.slider_label.setStyleSheet("font-size: 12px; color: white; background-color: #555; padding: 4px; border-radius: 5px;")

        # Connect slider movement to update the label
        self.value_slider.valueChanged.connect(lambda val: self.slider_label.setText(f"Delay: {val}"))

        # Game mode setup
        self.songs = {
            "Twinkle Twinkle": ["c4", "g4", "a4", "g4", "f4", "e4", "d4", "c4", "g4", "f4", "e4", "d4", "g4", "f4", "e4", "d4", "c4", "g4", "a4", "g4", "f4", "e4", "d4", "c4"],
            "Happy Birthday": ["c4", "d4", "c4", "f4", "e4", "c4", "d4", "c4", "g4", "f4"],
            "Mary Had a Little Lamb": ["e4", "d4", "c4", "d4", "e4", "d4", "e4", "g4", "e4", "d4", "c4", "d4", "e4", "d4", "e4", "d4", "c4"],
        }
        self.score = 0
        # Define the expected chord for each note
        self.note_to_chord = {
            "c4": {"c4", "e4", "g4"},
            "d4": {"d4", "f4", "a4"},
            "e4": {"e4", "g4", "b4"},
            "f4": {"f4", "a4", "c5"},
            "g4": {"g4", "b4", "d5"},
            "a4": {"a4", "c5", "e5"},
        }

        # Map notes to finger position images
        self.note_to_image = {
            "c4": "static/images/1.jpg",
            "d4": "static/images/2.jpg",
            "e4": "static/images/3.jpg",
            "f4": "static/images/4.jpg",
            "g4": "static/images/5.jpg",
            "a4": "static/images/6.jpg"
        }

        # Load finger position images
        self.finger_images = {}
        for note, img_path in self.note_to_image.items():
            try:
                img = cv2.imread(img_path)
                if img is not None:
                    self.finger_images[note] = img
                    print(f"Loaded image for {note}: {img_path}")
                else:
                    print(f"Failed to load image: {img_path}")
            except Exception as e:
                print(f"Error loading image {img_path}: {e}")
        self.last_hand_landmarks = None  
        self.counter = 0
        self.game_mode = False
        self.testing_mode = False
        self.test_signal_time = 0  # For latency measurement in testing mode
        self.previous_pattern = None  # Track previous pattern for gesture switch timing
        self.last_pattern_time = 0  # Track when last pattern was detected
        self.current_note_index = 0
        self.wrong_chord_flash = False
        self.flash_start_time = 0
        self.previous_selected_notes = set()  # Track previous finger pattern
        self.current_chord_correct = True  # Track if current chord is correct
        self.last_chord_change_time = 0
        self.chord_debounce_time = 0.5  
        self.game_song_dropdown = QComboBox()
        self.game_song_dropdown.addItems(self.songs.keys())
        self.game_song_dropdown.currentIndexChanged.connect(self.on_game_song_change)
        self.game_song_dropdown.setMinimumWidth(100)
        self.game_song_dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.game_song_dropdown.setStyleSheet("""
            QComboBox {
                background-color: #9C27B0;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QComboBox:hover {
                background-color: #7B1FA2;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #9C27B0;
                color: white;
                selection-background-color: #7B1FA2;
            }
        """)

        # Layout setup - controls on left, video on right
        main_layout = QHBoxLayout()

        # Left side - vertical layout for controls
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.Camera_button)
        left_layout.addWidget(self.mode_dropdown)
        left_layout.addWidget(self.Overlap_sounds_button)
        left_layout.addWidget(self.velocity_button)
        left_layout.addWidget(self.slider_label)
        left_layout.addWidget(self.value_slider)
        left_layout.addWidget(self.game_mode_button)
        left_layout.addWidget(self.game_song_dropdown)  # Song dropdown right after game mode button
        left_layout.addStretch()  # Push buttons to top

        # Right side - vertical layout for video and status
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.video_label)
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.song_notes_label)

        # Add left and right layouts to main layout
        # Set stretch factors: left panel gets less space, right panel (video) gets more
        main_layout.addLayout(left_layout, 1)  # Left panel gets 1 part
        main_layout.addLayout(right_layout, 4)  # Right panel gets 4 parts

        self.setLayout(main_layout)

        # State
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: asyncio.create_task(self.update_frame()))
        self.active_notes = set()
        self.selected_notes = set()
        self.currently_playing = set()
        self.new_strum_flag = [False]  # <- mutable boolean
        self.stop_sound_flag = [False]  # <- mutable boolean
        self.velocity = [0.0]
        self.sound_overlapping = False
        self.use_velocity = False  # Toggle between velocity-based and slider-based delay
        self.pattern_recognition_time = 0
        self.current_pattern_display = None  # Store current pattern for non-game mode display

        # Map pattern numbers to their primary note for image display
        self.pattern_to_note = {
            1: "c4",
            2: "d4",
            3: "e4",
            4: "f4",
            5: "g4",
            6: "a4"
        }

        # Audio
        try:
            self.sound = sa.WaveObject.from_wave_file("beep.wav")
        except Exception:
            self.sound = None
            print("No beep.wav found – sound disabled.")
        # buffer
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self.load_audio_files(self.mode_dropdown.currentText())

        # BLE
        self.ble = None

    def handle_ble_notification(self, decoded: str):
        """Called in Qt event loop - safe to update UI and flags"""
        print(f"BLE Notification: {decoded}", file=sys.stderr, flush=True)
        # self.status_label.setText(f"BLE: {decoded}")
        items = decoded.strip().split(",")
        if items[0] == "1":
            self.new_strum_flag[0] = True
            self.velocity[0] = float(items[1]) if len(items) > 1 else 0.0
            self.counter+=1
            print(self.counter)
        if items[0] == "0":
            self.stop_sound_flag[0] = True

    def keyPressEvent(self, event):
        """Handle keyboard events - space bar triggers strum when testing mode is enabled"""
        if event.key() == Qt.Key_Space and self.testing_mode:
            print("Space bar pressed - simulating BLE strum signal")
            # Record timestamp when simulated signal is sent
            self.test_signal_time = time.time()
            self.handle_ble_notification("1,0.8")  # Simulate signal with velocity
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Handle key release events"""
        if event.key() == Qt.Key_Up:
            # Release up key to stop sounds (set stop flag to True)
            self.handle_ble_notification("0, 0.8")
            print("Up key released - stop flag set to True")
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def load_audio_files(self, mode):
        try:
            if mode == "piano":
                self.c4 = pygame.mixer.Sound("static/audio/c4.mp3")
                self.d4 = pygame.mixer.Sound("static/audio/d4.mp3")
                self.e4 = pygame.mixer.Sound("static/audio/e4.mp3")
                self.f4 = pygame.mixer.Sound("static/audio/f4.mp3")
                self.g4 = pygame.mixer.Sound("static/audio/g4.mp3")
                self.a4 = pygame.mixer.Sound("static/audio/a4.mp3")
                self.b4 = pygame.mixer.Sound("static/audio/b4.mp3")
                self.c5 = pygame.mixer.Sound("static/audio/c5.mp3")
                self.d5 = pygame.mixer.Sound("static/audio/d5.mp3")
                self.e5 = pygame.mixer.Sound("static/audio/e5.mp3")
            elif mode == "lisa":
                self.c4 = pygame.mixer.Sound("static/audio/lisa-a3.mp3")
                self.d4 = pygame.mixer.Sound("static/audio/lisa-b3.mp3")
                self.e4 = pygame.mixer.Sound("static/audio/lisa-c4.mp3")
                self.f4 = pygame.mixer.Sound("static/audio/lisa-d4.mp3")
                self.g4 = pygame.mixer.Sound("static/audio/lisa-e4.mp3")
                self.a4 = pygame.mixer.Sound("static/audio/lisa-f4.mp3")
                self.b4 = pygame.mixer.Sound("static/audio/lisa-g4.mp3")
                self.c5 = pygame.mixer.Sound("static/audio/lisa-a4.mp3")
                self.d5 = None
                self.e5 = None
            elif mode == "guitar":
                print("Loading guitar audio files...")
                self.c4 = pygame.mixer.Sound("static/audio/guitar-c3.wav")
                self.d4 = pygame.mixer.Sound("static/audio/guitar-d4.wav")
                self.e4 = pygame.mixer.Sound("static/audio/guitar-e4.wav")
                self.f4 = pygame.mixer.Sound("static/audio/guitar-f4.wav")
                self.g4 = pygame.mixer.Sound("static/audio/guitar-g4.wav")
                self.a4 = pygame.mixer.Sound("static/audio/guitar-a4.wav")
                self.b4 = pygame.mixer.Sound("static/audio/guitar-b4.wav")
                self.c5 = pygame.mixer.Sound("static/audio/guitar-c4.wav")
                self.d5 = pygame.mixer.Sound("static/audio/guitar-d5.wav")
                self.e5 = pygame.mixer.Sound("static/audio/guitar-e5.wav")
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
            self.Camera_button.setText("Start\nCamera")
        else:
            self.cap = cv2.VideoCapture(0)
            self.timer.start(30)
            self.Camera_button.setText("Stop\nCamera")
    
    def toggle_game_mode(self):
        if not self.game_mode:
            self.game_mode = True
            self.game_mode_button.setText("Game\nMode\nON")
            self.song_notes_label.show()
            self.current_note_index = 0
            self.score = 0
            self.update_song_display()
        else:
            self.game_mode = False
            self.game_mode_button.setText("Game\nMode\nOFF")
            self.song_notes_label.hide()
    
    def overlap_sounds(self):
        if not self.sound_overlapping:
            self.Overlap_sounds_button.setText("Overlap ON")
            self.sound_overlapping = True
        else:
            self.sound_overlapping = False
            self.Overlap_sounds_button.setText("Overlap OFF")

    def toggle_velocity(self):
        if not self.use_velocity:
            self.velocity_button.setText("Velocity\nMode")
            self.use_velocity = True
        else:
            self.use_velocity = False
            self.velocity_button.setText("Slider\nMode")

    def on_dropdown_change(self, index):
        selected_mode = self.mode_dropdown.currentText()
        self.load_audio_files(selected_mode)
    
    def on_game_song_change(self, index):
        selected_song = self.game_song_dropdown.currentText()
        print(f"Selected song: {selected_song}")
        self.current_song = self.songs[selected_song]
        self.current_note_index = 0
        self.currently_playing.clear()
        self.selected_notes.clear()
        self.score = 0
        if self.game_mode:
            self.update_song_display()

    def update_song_display(self):
        selected_song = self.game_song_dropdown.currentText()
        notes = self.songs[selected_song]
        notes_text = " → ".join(notes)
        self.song_notes_label.setText(f"🎵 {selected_song}:\n{notes_text}")

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

    async def play_notes_with_delay(self, to_start):
        print("self.use_velocity", self.use_velocity)

        # Convert to list for indexed iteration
        notes_list = list(to_start)

        for i, note in enumerate(notes_list):
            # Only add delay BETWEEN notes, not before the first one
            if i > 0:
                if self.use_velocity:
                    velocity = self.velocity[0]
                    velocity = min(1.2, velocity)
                    ms_delay = max(0.01, max(0.1, 1.2 - velocity * 0.15))
                else:
                    # Use slider value for delay
                    selected_value = self.value_slider.value()
                    ms_delay = ((selected_value-1)*7)/1000.0
                await asyncio.sleep(ms_delay)
                print(f"Delay before note {note}: {ms_delay*1000:.1f}ms")

            # Play the note
            # if note is not none, stop/play
            if getattr(self, note) is None:
                print(f"Note {note} audio not loaded.")
                continue
            # getattr(self, note).stop()
            getattr(self, note).play()

            # Measure and print latency for first note in testing mode
            if i == 0 and self.testing_mode and hasattr(self, 'test_signal_time'):
                latency_ms = (time.time() - self.test_signal_time) * 1000
                print(f"⏱️  LATENCY: {latency_ms:.2f}ms (signal → sound)")
            # print(f"pattern to sound play: {time.time() - self.pattern_recognition_time:.5f}s")
        
    async def update_frame(self):
        if self.cap is None:
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        # Start timing for detection lag measurement
        frame_start_time = time.time()

        frame = cv2.flip(frame, 1)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame)
        # print "landmarks are changing" if landmarks changed from last time
        if results.multi_hand_landmarks != self.last_hand_landmarks:
            # print("Landmarks changed")
            self.last_hand_landmarks = results.multi_hand_landmarks

         # Analyze hand landmarks

        finger_text = "No hand detected"
        pattern_text = ""
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
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Straight", "Straight", "Straight", "Straight", "Straight"], ["g4", "b4", "d5"]),
                    (["Thumb", "Index", "Middle", "Ring", "Pinky"], ["Straight", "Bent", "Bent", "Bent", "Bent"], ["a4", "c5", "e5"]),
                ]
                self.currently_playing.clear()
                current_pattern = None
                for pattern_idx, (fingers, states_list, notes) in enumerate(patterns, start=1):
                    if all(states[f] == s for f, s in zip(fingers, states_list)):
                        self.selected_notes.update(notes)
                        current_time = time.time()
                        self.pattern_recognition_time = current_time

                        if pattern_idx == 4:
                            current_pattern = 3
                        elif pattern_idx > 4:
                            current_pattern = pattern_idx - 1
                        else:
                            current_pattern = pattern_idx

                        # Measure detection lag (frame capture to pattern detection)
                        detection_lag_ms = (current_time - frame_start_time) * 1000

                        # Measure gesture switch time if pattern changed
                        if self.previous_pattern is not None and current_pattern != self.previous_pattern:
                            switch_time_ms = (current_time - self.last_pattern_time) * 1000
                            # print(f"🔄 GESTURE SWITCH: Pattern {self.previous_pattern} → {current_pattern}")
                            # print(f"   Total switch time: {switch_time_ms:.2f}ms | Detection lag: {detection_lag_ms:.2f}ms")
                        # elif self.testing_mode:
                        #     # In testing mode, show detection lag for every frame
                        #     print(f"⚡ DETECTION LAG: {detection_lag_ms:.2f}ms (frame → pattern {current_pattern})")

                        self.previous_pattern = current_pattern
                        self.last_pattern_time = current_time
                        break

                # Update pattern text
                if current_pattern is not None:
                    pattern_text = f" | Pattern {current_pattern}"
                    self.current_pattern_display = current_pattern  # Store for display

                # Track if pattern changed
                pattern_changed = self.selected_notes != self.previous_selected_notes

                to_stop = set()
                
                # Check BLE event flag (strum detected)
                if self.new_strum_flag[0]:
                    to_stop = self.active_notes
                    self.currently_playing = self.selected_notes.copy()
                    self.active_notes = self.currently_playing.copy()
                    
                    if self.game_mode and self.selected_notes:
                        selected_song = self.game_song_dropdown.currentText()
                        song_notes = self.songs[selected_song]
                        
                        if self.current_note_index < len(song_notes):
                            current_note = song_notes[self.current_note_index]
                            expected_chord = self.note_to_chord.get(current_note, {current_note})

                            if self.selected_notes == expected_chord:
                                # Correct chord!
                                self.current_note_index += 1
                                self.score += 1
                                print(f"✓ Correct chord! Moving to note {self.current_note_index}")
                                self.wrong_chord_flash = False
                                self.current_chord_correct = True
                            elif pattern_changed:
                                # Wrong chord - trigger red flash
                                self.wrong_chord_flash = True
                                self.flash_start_time = time.time()
                                self.current_chord_correct = False
                                self.current_note_index += 1
                                print(f"✗ Wrong chord! Expected {expected_chord}, got {self.selected_notes}")
                        
                        # Update previous pattern after validation
                        self.previous_selected_notes = self.selected_notes.copy()
                    
                    
                    
                elif self.stop_sound_flag[0]:
                    to_stop = self.active_notes
                    self.active_notes = set()
                    # self.stop_sound_flag[0] = False  # reset flag
                
                if self.sound_overlapping:
                    for note in to_stop:
                        if getattr(self, note) is not None and note in self.currently_playing:
                            getattr(self, note).stop()
                elif not self.sound_overlapping and self.new_strum_flag[0]:
                    for note in to_stop:
                        if getattr(self, note) is not None:
                            getattr(self, note).stop()
                if self.stop_sound_flag[0]:
                    for note in to_stop:
                        if getattr(self, note) is not None:
                            getattr(self, note).stop()
                self.new_strum_flag[0] = False  # reset flag
                self.stop_sound_flag[0] = False  # reset flag
                
                to_start = self.currently_playing
                

                if to_start:
                    # Play the notes on strum (only if not in game mode OR chord is correct)
                    should_play = not self.game_mode or self.current_chord_correct
                    if should_play:
                        asyncio.create_task(self.play_notes_with_delay(to_start))
                    else:
                        print("✗ Not playing - wrong chord held")

                self.currently_playing = set()
                self.selected_notes = set()

        self.status_label.setText(f"Finger Status: {finger_text}\n{pattern_text}")

        if self.game_mode:
            selected_song = self.game_song_dropdown.currentText()
            song_notes = self.songs[selected_song]
            if self.current_note_index < len(song_notes):
                current_note = song_notes[self.current_note_index]
                text = f"Play: {current_note.upper()[0]}"
                font = cv2.FONT_HERSHEY_DUPLEX
                font_scale = 2.5
                thickness = 4
                (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)

                frame_h, frame_w = frame.shape[:2]
                x = (frame_w - text_width) // 2
                y = 80
                padding = 15
                cv2.rectangle(frame,
                            (x - padding, y - text_height - padding),
                            (x + text_width + padding, y + baseline + padding),
                            (0, 0, 0), -1)

                cv2.putText(frame, text, (x, y), font, font_scale, (0, 255, 0), thickness)

                # Display finger position image if available
                if current_note in self.finger_images:
                    finger_img = self.finger_images[current_note]
                    # Resize image to fit nicely on screen (e.g., 200x200)
                    img_h, img_w = finger_img.shape[:2]
                    target_size = 200
                    scale = target_size / max(img_h, img_w)
                    new_w, new_h = int(img_w * scale), int(img_h * scale)
                    resized_img = cv2.resize(finger_img, (new_w, new_h))

                    # Position image at top-right corner
                    img_x = frame_w - new_w - 20
                    img_y = 20

                    # Overlay image on frame
                    frame[img_y:img_y+new_h, img_x:img_x+new_w] = resized_img
            else:
                # Song completed
                text = f"SONG COMPLETE!\n Score: {self.score}/{len(song_notes)}"
                font = cv2.FONT_HERSHEY_DUPLEX
                font_scale = 2.0
                thickness = 4
                (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
                frame_h, frame_w = frame.shape[:2]
                x = (frame_w - text_width) // 2
                y = frame_h // 2
                padding = 15
                cv2.rectangle(frame,
                            (x - padding, y - text_height - padding),
                            (x + text_width + padding, y + baseline + padding),
                            (0, 0, 0), -1)
                cv2.putText(frame, text, (x, y), font, font_scale, (0, 255, 255), thickness)
        else:
            # Non-game mode: Display current pattern and notes
            if hasattr(self, 'current_pattern_display') and self.current_pattern_display is not None:
                frame_h, frame_w = frame.shape[:2]

                # Display pattern number (centered)
                text = f"{self.pattern_to_note[self.current_pattern_display][0].upper()} (Pattern {self.current_pattern_display})"
                font = cv2.FONT_HERSHEY_DUPLEX
                font_scale = 2.5
                thickness = 4
                (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
                (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)

                x = (frame_w - text_width) // 2
                y = 100
                padding = 15
                cv2.rectangle(frame,
                            (x - padding, y - text_height - padding),
                            (x + text_width + padding, y + baseline + padding),
                            (0, 0, 0), -1)

                cv2.putText(frame, text, (x, y), font, font_scale, (0, 200, 255), thickness)

                if self.active_notes:
                    notes_text = " + ".join([note.upper() for note in sorted(self.active_notes)])
                    notes_display = f"Playing: {notes_text}"
                    font_scale_notes = 1.2
                    thickness_notes = 2
                    (notes_width, notes_height), notes_baseline = cv2.getTextSize(notes_display, font, font_scale_notes, thickness_notes)

                    x_notes = (frame_w - notes_width) // 2  # Center horizontally
                    y_notes = y + 80
                    cv2.rectangle(frame,
                                (x_notes - padding, y_notes - notes_height - padding),
                                (x_notes + notes_width + padding, y_notes + notes_baseline + padding),
                                (0, 0, 0), -1)

                    cv2.putText(frame, notes_display, (x_notes, y_notes), font, font_scale_notes, (0, 255, 0), thickness_notes)

                if self.current_pattern_display in self.pattern_to_note:
                    note_for_image = self.pattern_to_note[self.current_pattern_display]
                    if note_for_image in self.finger_images:
                        finger_img = self.finger_images[note_for_image]
                        img_h, img_w = finger_img.shape[:2]
                        target_size = 200
                        scale = target_size / max(img_h, img_w)
                        new_w, new_h = int(img_w * scale), int(img_h * scale)
                        resized_img = cv2.resize(finger_img, (new_w, new_h))

                        img_x = frame_w - new_w - 20
                        img_y = 20

                        frame[img_y:img_y+new_h, img_x:img_x+new_w] = resized_img

        # Red flash overlay for wrong chords
        if self.wrong_chord_flash:
            flash_duration = 0.3 
            elapsed = time.time() - self.flash_start_time
            if elapsed < flash_duration:
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]), (255, 0, 0), -1)
                alpha = 0.3
                frame = cv2.addWeighted(frame, 1 - alpha, overlay, alpha, 0)
            else:
                self.wrong_chord_flash = False

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
        print("Setting up BLE...")
        start = time.perf_counter()
        await win.init_ble()
        end = time.perf_counter()
        print(f"BLE initialized and notifications handler created in {end - start:.2f} seconds")
    

    # Enable testing mode (space bar to trigger strum)
    win.testing_mode = True

    # loop.create_task(setup())
    win.show()
    
    with loop:
        sys.exit(loop.run_forever())
