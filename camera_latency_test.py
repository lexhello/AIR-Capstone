import cv2
import time

cap = cv2.VideoCapture(0)

# Warm up camera to avoid auto-exposure delay
for _ in range(10):
    cap.read()

latencies = []

for _ in range(100):
    start = time.time()
    ret, frame = cap.read()
    end = time.time()

    latencies.append((end - start) * 1000)  # ms

cap.release()

print("Avg latency:  ", sum(latencies) / len(latencies), "ms")
print("Max latency:  ", max(latencies), "ms")
print("Min latency:  ", min(latencies), "ms")
