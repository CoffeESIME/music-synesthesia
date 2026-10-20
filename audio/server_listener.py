"""Carga el audio nativo solo cuando se solicita la escucha del servidor."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audio.pitch_detector import AudioListener


class ServerAudioListener:
    def __init__(self) -> None:
        self._listener: AudioListener | None = None

    def start(self) -> None:
        try:
            from audio.pitch_detector import AudioListener
        except ImportError as error:
            raise RuntimeError(
                "La escucha del servidor requiere requirements-hardware.txt. "
                "Tambien puedes usar el microfono del navegador."
            ) from error
        self._listener = AudioListener()
        self._listener.start()

    def listen_for_note(self) -> str | None:
        if self._listener is None:
            raise RuntimeError("El microfono del servidor no esta iniciado")
        return self._listener.listen_for_note()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
