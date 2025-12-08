import librosa
import soundfile as sf

def pitch_shift_note(input_file, output_file, semitones):
    high_sr = 48000
    audio, sr = librosa.load(input_file, sr=high_sr)

    shifted = librosa.effects.pitch_shift(
        y=audio,
        sr=sr,
        n_steps=semitones
    )

    sf.write(output_file, shifted, sr)
    print("Saved:", output_file)

input_file = "static/audio/guitar-c4-old.wav"

pitch_shift_note(input_file, "static/audio/guitar-d5.wav", 2)
pitch_shift_note(input_file, "static/audio/guitar-e5.wav", 4)
