import numpy as np
import matplotlib.pyplot as plt

# Generate velocity values to test the full range
velocities = np.linspace(0, 1.2, 400)

ms_delay_values = []

for v in velocities:
    velocity = min(1.2, v)
    ms_delay = max(0.01, max(0.1, 1.2 - velocity * 0.15))
    ms_delay_values.append(ms_delay)

plt.figure(figsize=(8, 5))
plt.plot(velocities, ms_delay_values)
plt.xlabel("Velocity")
plt.ylabel("ms_delay")
plt.title("ms_delay as a Function of Velocity")
plt.grid(True)
plt.show()
