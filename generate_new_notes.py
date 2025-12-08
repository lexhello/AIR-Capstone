import librosa
import soundfile as sf

def pitch_shift_note(input_file, output_file, semitones):
    audio, sr = librosa.load(input_file, sr=None)

    shifted = librosa.effects.pitch_shift(
        y=audio,
        sr=sr,
        n_steps=semitones
    )

    sf.write(output_file, shifted, sr)
    print("Saved:", output_file)

input_file = "static/audio/guitar-c4.wav"

pitch_shift_note(input_file, "static/audio/guitar-d5.wav", 14)
pitch_shift_note(input_file, "static/audio/guitar-e5.wav", 16)
