import pygame
import time

# --- Initialize mixer ---
pygame.mixer.init()

# --- Load sound ---
sound = pygame.mixer.Sound("example.wav")

# --- Parameters ---
fade_durations = [3.0, 5.0, 7.0]   # seconds to fade each sound out
start_volumes = [1.0, 0.8, 0.6]
delays = [0.0, 0.5, 1.0]           # stagger start times
channels = []

# --- Helper to play sound on a free channel ---
def play_fading_sound(sound, start_volume, fade_duration):
    ch = sound.play()
    if ch:
        ch.set_volume(start_volume)
    return {"channel": ch, "volume": start_volume, "fade_duration": fade_duration, "start_time": time.time()}

# --- Start overlapping sounds ---
for fade, vol, delay in zip(fade_durations, start_volumes, delays):
    time.sleep(delay)
    sound_info = play_fading_sound(sound, vol, fade)
    if sound_info["channel"]:
        channels.append(sound_info)
        print(f"Started sound: fade={fade}s, start_volume={vol}, delay={delay}s")

# --- Real-time fade control loop ---
running = True
update_rate = 0.05  # seconds per update frame

while running:
    now = time.time()
    active_channels = []

    for s in channels:
        ch = s["channel"]
        if ch and ch.get_busy():
            elapsed = now - s["start_time"]
            fade_ratio = elapsed / s["fade_duration"]
            new_vol = max(0.0, s["volume"] * (1.0 - fade_ratio))  # linear fade
            # new_vol = s["volume"] * (1.0 - fade_ratio) ** 2  # quadratic fade
            ch.set_volume(new_vol)
            # print(f"Volume: {new_vol:.2f}")
            if new_vol > 0:
                active_channels.append(s)

    channels = active_channels
    if not channels:
        running = False  # stop when all faded out
    time.sleep(update_rate)

pygame.mixer.quit()
print("All sounds faded out and finished.")
