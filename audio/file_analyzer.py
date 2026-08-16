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


def _rgb_to_hex(rgb: list[int]) -> str:
    """Convierte una lista RGB validada a hexadecimal."""
    if len(rgb) != 3 or any(channel < 0 or channel > 255 for channel in rgb):
        raise ValueError("Cada color del perfil debe contener tres canales de 0 a 255")
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def analyze_audio_file(
    filepath: str,
    profile: dict[str, list[int]],
) -> list[dict[str, float | str]]:
    """Genera cues temporales de nota y color para una pista WAV o MP3."""
    if not profile:
        raise ValueError("El perfil sinestesico no puede estar vacio")

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
    lighting_map: list[dict[str, float | str]] = []
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
        if note not in profile:
            raise ValueError(f"El perfil no contiene un color para la nota {note}")

        time_sec: float = float(
            librosa.frames_to_time(
                start_frame,
                sr=sample_rate,
                hop_length=HOP_LENGTH,
            )
        )
        lighting_map.append(
            {
                "time_sec": round(time_sec, 3),
                "color_hex": _rgb_to_hex(profile[note]),
                "note": note,
            }
        )
        previous_note = note

    return lighting_map
