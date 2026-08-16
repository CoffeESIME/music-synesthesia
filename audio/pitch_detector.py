"""Captura de microfono y deteccion de la nota musical fundamental."""

from __future__ import annotations

import math
from types import TracebackType
from typing import Protocol, cast

import aubio
import numpy as np
from numpy.typing import NDArray
import pyaudio


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


class _PitchEstimator(Protocol):
    """Interfaz minima del estimador creado por aubio.pitch."""

    def __call__(self, samples: NDArray[np.float32]) -> NDArray[np.float32]: ...

    def get_confidence(self) -> float: ...

    def set_tolerance(self, tolerance: float) -> None: ...

    def set_unit(self, unit: str) -> None: ...


def hz_to_note(hz: float) -> str:
    """Convierte una frecuencia positiva a la nota cromatica mas cercana."""
    if not math.isfinite(hz) or hz <= 0.0:
        raise ValueError("La frecuencia debe ser un numero positivo y finito")

    midi_note: int = round(69 + 12 * math.log2(hz / 440.0))
    return NOTE_NAMES[midi_note % len(NOTE_NAMES)]


class AudioListener:
    """Lee audio mono del microfono y detecta su frecuencia fundamental."""

    def __init__(
        self,
        sample_rate: int = 44_100,
        window_size: int = 2_048,
        hop_size: int = 1_024,
        noise_threshold: float = 0.01,
        min_confidence: float = 0.80,
        input_device_index: int | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate debe ser mayor que cero")
        if window_size <= 0 or hop_size <= 0:
            raise ValueError("window_size y hop_size deben ser mayores que cero")
        if window_size < hop_size:
            raise ValueError("window_size debe ser mayor o igual que hop_size")
        if noise_threshold < 0.0:
            raise ValueError("noise_threshold no puede ser negativo")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence debe estar entre 0 y 1")

        self.sample_rate: int = sample_rate
        self.window_size: int = window_size
        self.hop_size: int = hop_size
        self.noise_threshold: float = noise_threshold
        self.min_confidence: float = min_confidence
        self.input_device_index: int | None = input_device_index
        self.last_rms: float = 0.0

        estimator = aubio.pitch("yin", window_size, hop_size, sample_rate)
        self._pitch_estimator: _PitchEstimator = cast(_PitchEstimator, estimator)
        self._pitch_estimator.set_unit("Hz")
        self._pitch_estimator.set_tolerance(0.8)
        self._audio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None

    @property
    def is_running(self) -> bool:
        """Indica si el stream del microfono esta abierto."""
        return self._stream is not None

    def start(self) -> None:
        """Abre el stream mono de entrada del microfono."""
        if self._stream is not None:
            return

        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.hop_size,
                input_device_index=self.input_device_index,
            )
        except BaseException:
            audio.terminate()
            raise

        self._audio = audio
        self._stream = stream

    def read_frequency(self) -> float | None:
        """Lee un chunk y devuelve su frecuencia o None si no supera el gate."""
        if self._stream is None:
            raise RuntimeError("El AudioListener debe iniciarse antes de leer")

        raw_chunk: bytes = self._stream.read(
            self.hop_size,
            exception_on_overflow=False,
        )
        samples: NDArray[np.float32] = (
            np.frombuffer(raw_chunk, dtype=np.int16).astype(np.float32) / 32_768.0
        )
        self.last_rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))

        if self.last_rms < self.noise_threshold:
            return None

        frequency: float = float(self._pitch_estimator(samples)[0])
        confidence: float = float(self._pitch_estimator.get_confidence())
        if (
            not math.isfinite(frequency)
            or frequency <= 0.0
            or confidence < self.min_confidence
        ):
            return None

        return frequency

    def listen_for_note(self) -> str | None:
        """Lee un chunk y devuelve la nota detectada, o None si no es valida."""
        frequency: float | None = self.read_frequency()
        if frequency is None:
            return None
        return hz_to_note(frequency)

    def stop(self) -> None:
        """Cierra el stream y libera el dispositivo de audio."""
        stream: pyaudio.Stream | None = self._stream
        audio: pyaudio.PyAudio | None = self._audio
        self._stream = None
        self._audio = None

        if stream is not None:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
        if audio is not None:
            audio.terminate()

    def __enter__(self) -> AudioListener:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()
