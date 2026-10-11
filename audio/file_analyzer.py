"""Analisis estatico de pistas para generar un mapa de iluminacion."""

import librosa
import numpy as np
from numpy.typing import NDArray


NOTE_NAMES: tuple[str, ...] = (
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
)
SAMPLE_RATE: int = 22_050
HOP_LENGTH: int = 512
CUE_INTERVAL_SECONDS: float = 0.25


def analyze_audio_file(
    filepath: str,
) -> list[dict[str, float | str]]:
    """Extrae una linea de tiempo de notas de una pista WAV o MP3."""
    audio, sample_rate = librosa.load(filepath, sr=SAMPLE_RATE, mono=True)
    if audio.size == 0:
        raise ValueError("El archivo de audio no contiene muestras")

    chromagram: NDArray[np.float32] = librosa.feature.chroma_stft(
        y=audio,
        sr=sample_rate,
        hop_length=HOP_LENGTH,
    )
    frames_per_cue: int = max(
        1,
        round(CUE_INTERVAL_SECONDS * sample_rate / HOP_LENGTH),
    )
    timeline: list[dict[str, float | str]] = []
    previous_note: str | None = None

    for start_frame in range(0, chromagram.shape[1], frames_per_cue):
        end_frame: int = min(start_frame + frames_per_cue, chromagram.shape[1])
        segment: NDArray[np.float32] = chromagram[:, start_frame:end_frame]
        mean_chroma: NDArray[np.float32] = np.mean(segment, axis=1)
        if float(np.max(mean_chroma)) <= 1e-8:
            previous_note = None
            continue

        note: str = NOTE_NAMES[int(np.argmax(mean_chroma))]
        if note == previous_note:
            continue
        time_seconds: float = float(
            librosa.frames_to_time(
                start_frame,
                sr=sample_rate,
                hop_length=HOP_LENGTH,
            )
        )
        timeline.append(
            {
                "time": round(time_seconds, 3),
                "note": note,
            }
        )
        previous_note = note

    return timeline
