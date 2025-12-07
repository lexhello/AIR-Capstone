import numpy as np
from scipy.io import wavfile

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

# Example usage
reduce_volume("static/audio/guitar-a4-old.wav", "static/audio/guitar-a4.wav", reduction_factor=0.2)
reduce_volume("static/audio/guitar-b4-old.wav", "static/audio/guitar-b4.wav", reduction_factor=0.2)
reduce_volume("static/audio/guitar-c3-old.wav", "static/audio/guitar-c3.wav", reduction_factor=0.2)
reduce_volume("static/audio/guitar-c4-old.wav", "static/audio/guitar-c4.wav", reduction_factor=0.2)
reduce_volume("static/audio/guitar-d4-old.wav", "static/audio/guitar-d4.wav", reduction_factor=0.2)
reduce_volume("static/audio/guitar-e4-old.wav", "static/audio/guitar-e4.wav", reduction_factor=0.2)
reduce_volume("static/audio/guitar-f4-old.wav", "static/audio/guitar-f4.wav", reduction_factor=0.2)
reduce_volume("static/audio/guitar-g4-old.wav", "static/audio/guitar-g4.wav", reduction_factor=0.2)