import numpy as np
from scipy.io import wavfile

def apply_fade_out(data, fade_time, sample_rate):
    """Applies a linear fade-out over the last `fade_time` seconds."""
    fade_samples = int(fade_time * sample_rate)

    if fade_samples <= 1:
        return data  # too short to matter

    # Create fade envelope
    fade_curve = np.linspace(1.0, 0.0, fade_samples)

    # Apply to the last part of the audio
    data[-fade_samples:] *= fade_curve[:, None] if data.ndim > 1 else fade_curve

    return data

def reduce_volume(input_path, output_path, reduction_factor=0.7):
    """
    Loads a WAV file, reduces its volume, and saves it as a new WAV file.
    reduction_factor=0.7 means volume is reduced by 30%.
    """
    # Read sample rate and audio data
    sample_rate, data = wavfile.read(input_path)

    # Convert to float to avoid clipping during multiplication
    data_float = data.astype(np.float32)

    # Apply volume reduction
    data_reduced = data_float * reduction_factor

    # Convert back to original dtype (must clip to valid range)
    if data.dtype == np.int16:
        data_reduced = np.clip(data_reduced, -32768, 32767).astype(np.int16)
    elif data.dtype == np.int32:
        data_reduced = np.clip(data_reduced, -2147483648, 2147483647).astype(np.int32)
    else:
        # For float WAVs, just cast back
        data_reduced = data_reduced.astype(data.dtype)

    # Save output file
    wavfile.write(output_path, sample_rate, data_reduced)
    
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, filtfilt

def butter_highpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    return b, a

def reduce_low_frequencies(input_wav, output_wav, cutoff=200, reduction=0.5, fade_out_ms=10):
    fs, data = wavfile.read(input_wav)

    data = data.astype(np.float32)

    b, a = butter_highpass(cutoff, fs, order=6)
    high = filtfilt(b, a, data, axis=0)
    low = data - high
    low *= reduction

    output = high + low

    # Apply fade-out
    fade_seconds = fade_out_ms / 1000
    output = apply_fade_out(output, fade_seconds, fs)

    # Convert back to int16
    output = np.clip(output, -32768, 32767).astype(np.int16)

    wavfile.write(output_wav, fs, output)
    print("Saved with fade:", output_wav)

# Example usage:
reduce_low_frequencies("static/audio/guitar-a4-old.wav", "static/audio/guitar-a4.wav", cutoff=400, reduction=0.05, fade_out_ms=20)
reduce_low_frequencies("static/audio/guitar-b4-old.wav", "static/audio/guitar-b4.wav", cutoff=400, reduction=0.05, fade_out_ms=20)
reduce_low_frequencies("static/audio/guitar-c3-old.wav", "static/audio/guitar-c3.wav", cutoff=400, reduction=0.05, fade_out_ms=20)
reduce_low_frequencies("static/audio/guitar-c4-old.wav", "static/audio/guitar-c4.wav", cutoff=400, reduction=0.05, fade_out_ms=20)
reduce_low_frequencies("static/audio/guitar-d4-old.wav", "static/audio/guitar-d4.wav", cutoff=400, reduction=0.05, fade_out_ms=20)
reduce_low_frequencies("static/audio/guitar-e4-old.wav", "static/audio/guitar-e4.wav", cutoff=400, reduction=0.05, fade_out_ms=20)
reduce_low_frequencies("static/audio/guitar-f4-old.wav", "static/audio/guitar-f4.wav", cutoff=400, reduction=0.05, fade_out_ms=20)
reduce_low_frequencies("static/audio/guitar-g4-old.wav", "static/audio/guitar-g4.wav", cutoff=400, reduction=0.05, fade_out_ms=20)

# Example usage to just reduce volum
# reduce_volume("static/audio/guitar-a4-old.wav", "static/audio/guitar-a4.wav", reduction_factor=0.2)
# reduce_volume("static/audio/guitar-b4-old.wav", "static/audio/guitar-b4.wav", reduction_factor=0.2)
# reduce_volume("static/audio/guitar-c3-old.wav", "static/audio/guitar-c3.wav", reduction_factor=0.2)
# reduce_volume("static/audio/guitar-c4-old.wav", "static/audio/guitar-c4.wav", reduction_factor=0.2)
# reduce_volume("static/audio/guitar-d4-old.wav", "static/audio/guitar-d4.wav", reduction_factor=0.2)
# reduce_volume("static/audio/guitar-e4-old.wav", "static/audio/guitar-e4.wav", reduction_factor=0.2)
# reduce_volume("static/audio/guitar-f4-old.wav", "static/audio/guitar-f4.wav", reduction_factor=0.2)
# reduce_volume("static/audio/guitar-g4-old.wav", "static/audio/guitar-g4.wav", reduction_factor=0.2)