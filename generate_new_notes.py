import numpy as np
import soundfile as sf
import pyrubberband as rb

def generate_note(input_file, output_file, semitones, fade_ms=40):
    """High-quality guitar pitch shifting with fade-out."""
    
    # Load audio at native sample rate
    audio, sr = sf.read(input_file)

    # Pitch shift using Rubberband
    shifted = rb.pitch_shift(audio, sr, semitones)

    # Apply fade-out (prevents clicking at note end)
    shifted = apply_fade_out(shifted, fade_ms, sr)

    # Save output WAV
    sf.write(output_file, shifted, sr)
    print("Saved:", output_file)
    
def apply_fade_out(audio, fade_ms, sr):
    """Apply a linear fade-out for mono or stereo audio."""
    fade_samples = int(sr * (fade_ms / 1000.0))

    if fade_samples > len(audio):
        fade_samples = len(audio)

    fade_curve = np.linspace(1.0, 0.0, fade_samples)

    audio_out = audio.copy()

    # MONO
    if audio.ndim == 1:
        audio_out[-fade_samples:] *= fade_curve

    # STEREO OR MULTICHANNEL
    else:
        audio_out[-fade_samples:] *= fade_curve[:, None]

    return audio_out

# ---- INPUT RECORDING (C4) ----
input_file = "static/audio/guitar-c4-old.wav"

# ---- OUTPUT NOTES ----
generate_note(input_file, "static/audio/guitar-d5.wav", semitones=2)
generate_note(input_file, "static/audio/guitar-e5.wav", semitones=4)