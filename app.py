from flask import Flask, render_template, Response
from flask_socketio import SocketIO
import cv2
import mediapipe as mp
import threading
import time

# --- Flask & SocketIO Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

# --- MediaPipe Setup ---
mp_hands = mp.solutions.hands

mp_drawing = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,  # streaming mode
    max_num_hands=1,
    min_detection_confidence=0.5
)

# hands = mp_hands.Hands(
#     static_image_mode=False,
#     max_num_hands=1,
#     min_detection_confidence=0.5
# )

# --- Shared State ---
cooldown_active = False
COOLDOWN_DURATION = 1.0  # seconds

# --- Flask Route ---
@app.route('/')
def index():
    return render_template('index.html', title='MediaPipe Flask App')

# --- Frame Generator ---
def generate_frames():
    global cooldown_active
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    try:
        while True:
            time.sleep(0.03)
            success, frame = cap.read()
            # print("Frame read:", success)
            if not success:
                break

            # Flip for selfie view
            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(frame_rgb)

            left_hand_detected = False

            if results.multi_hand_landmarks:
                for idx, handedness in enumerate(results.multi_handedness):
                    hand_label = handedness.classification[0].label
                    mp_drawing.draw_landmarks(
                        frame,
                        results.multi_hand_landmarks[idx],
                        mp_hands.HAND_CONNECTIONS
                    )
                    if hand_label == 'Left':
                        left_hand_detected = True

            # Emit detection event (with cooldown)
            if left_hand_detected and not cooldown_active:
                socketio.emit('detection_event', {'hand': 'left'}, namespace='/')
                cooldown_active = True
                threading.Timer(COOLDOWN_DURATION, lambda: globals().update(cooldown_active=False)).start()

            # Encode frame for MJPEG streaming
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            time.sleep(0.02)  # Small delay to reduce CPU usage

    finally:
        cap.release()
        print("Camera released.")

# --- Video Feed Route ---
@app.route('/video_feed')
def video_feed():
    """MJPEG video stream route."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# --- SocketIO Connect Event ---
@socketio.on('connect')
def handle_connect():
    print("Client connected!")

# --- Run App ---
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
    # socketio.run(app, debug=True, port=5000)
