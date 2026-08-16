"""Motor no bloqueante que conecta la deteccion de audio con Philips Hue."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import logging
import threading
from typing import Protocol

from core.synesthesia import PERFILES


LOGGER: logging.Logger = logging.getLogger(__name__)


class AudioSource(Protocol):
    """Contrato requerido del adaptador de entrada de audio."""

    def start(self) -> None: ...

    def listen_for_note(self) -> str | None: ...

    def stop(self) -> None: ...


class LightAdapter(Protocol):
    """Contrato requerido del adaptador de salida para luces."""

    def set_color(
        self,
        light_id: str,
        rgb: tuple[int, int, int],
        transition_ms: int = 400,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class ColorEvent:
    """Ultima correspondencia valida producida por el motor."""

    note: str
    rgb: tuple[int, int, int]

    @property
    def hex_color(self) -> str:
        """Devuelve el color RGB en formato hexadecimal para la futura UI."""
        return "#{:02X}{:02X}{:02X}".format(*self.rgb)


class SynesthesiaEngine:
    """Administra en un hilo daemon el flujo audio -> perfil -> luces."""

    def __init__(
        self,
        listener: AudioSource,
        hue_controller: LightAdapter,
        light_ids: Sequence[str],
        profile_name: str = "scriabin",
        transition_ms: int = 100,
    ) -> None:
        normalized_ids: tuple[str, ...] = tuple(
            light_id.strip() for light_id in light_ids if light_id.strip()
        )
        if not normalized_ids:
            raise ValueError("Debe proporcionarse al menos un light_id")
        if transition_ms < 0:
            raise ValueError("transition_ms no puede ser negativo")

        normalized_profile: str = self._normalize_profile(profile_name)
        self._listener: AudioSource = listener
        self._hue_controller: LightAdapter = hue_controller
        self._light_ids: tuple[str, ...] = normalized_ids
        self._transition_ms: int = transition_ms
        self._profile_name: str = normalized_profile
        self._stop_event: threading.Event = threading.Event()
        self._state_lock: threading.RLock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._last_event: ColorEvent | None = None
        self._last_error: str | None = None

    @staticmethod
    def _normalize_profile(profile_name: str) -> str:
        normalized_profile: str = profile_name.strip().lower()
        if normalized_profile not in PERFILES:
            available: str = ", ".join(sorted(PERFILES))
            raise ValueError(f"Perfil desconocido. Disponibles: {available}")
        return normalized_profile

    @property
    def is_running(self) -> bool:
        """Indica si el hilo administrador sigue activo."""
        with self._state_lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def active_profile(self) -> str:
        """Devuelve el nombre normalizado del perfil actual."""
        with self._state_lock:
            return self._profile_name

    @property
    def last_event(self) -> ColorEvent | None:
        """Devuelve el ultimo color detectado de forma segura entre hilos."""
        with self._state_lock:
            return self._last_event

    @property
    def last_error(self) -> str | None:
        """Devuelve el ultimo error del worker, si existe."""
        with self._state_lock:
            return self._last_error

    def set_profile(self, profile_name: str) -> None:
        """Cambia atomicamente el perfil que usara el siguiente chunk."""
        normalized_profile: str = self._normalize_profile(profile_name)
        with self._state_lock:
            self._profile_name = normalized_profile

    def apply_track_color(
        self,
        note: str,
        rgb: tuple[int, int, int],
        transition_ms: int = 100,
    ) -> ColorEvent:
        """Aplica de forma sincrona un cue de pista mediante el adaptador Hue."""
        if not note.strip():
            raise ValueError("note no puede estar vacia")
        if transition_ms < 0:
            raise ValueError("transition_ms no puede ser negativo")

        event = ColorEvent(note=note, rgb=rgb)
        errors: list[str] = []
        with self._state_lock:
            self._last_event = event

        for light_id in self._light_ids:
            try:
                self._hue_controller.set_color(
                    light_id,
                    rgb,
                    transition_ms=transition_ms,
                )
            except Exception as error:
                errors.append(f"{light_id}: {error}")

        with self._state_lock:
            self._last_error = "; ".join(errors) if errors else None
        if errors:
            raise RuntimeError("; ".join(errors))
        return event

    def start(self) -> bool:
        """Inicia el hilo daemon; devuelve False si ya estaba activo."""
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return False

            self._stop_event.clear()
            self._last_error = None
            thread = threading.Thread(
                target=self._run,
                name="synesthesia-engine",
                daemon=True,
            )
            self._thread = thread
            thread.start()
            return True

    def stop(self, timeout_seconds: float = 3.0) -> bool:
        """Solicita detener el worker y espera su cierre hasta el timeout."""
        if timeout_seconds < 0.0:
            raise ValueError("timeout_seconds no puede ser negativo")

        self._stop_event.set()
        with self._state_lock:
            thread: threading.Thread | None = self._thread

        if thread is None:
            return True
        if thread is threading.current_thread():
            return False

        thread.join(timeout_seconds)
        return not thread.is_alive()

    def _get_rgb(self, note: str) -> tuple[int, int, int] | None:
        with self._state_lock:
            profile_name: str = self._profile_name
        values: list[int] | None = PERFILES[profile_name].get(note)
        if values is None:
            return None
        return (values[0], values[1], values[2])

    def _run(self) -> None:
        last_note: str | None = None
        try:
            self._listener.start()
            while not self._stop_event.is_set():
                note: str | None = self._listener.listen_for_note()
                if note is None:
                    last_note = None
                    continue
                if note == last_note:
                    continue

                rgb: tuple[int, int, int] | None = self._get_rgb(note)
                if rgb is None:
                    continue

                last_note = note
                event = ColorEvent(note=note, rgb=rgb)
                with self._state_lock:
                    self._last_event = event

                for light_id in self._light_ids:
                    try:
                        self._hue_controller.set_color(
                            light_id,
                            rgb,
                            transition_ms=self._transition_ms,
                        )
                    except Exception as error:
                        error_message: str = str(error)
                        with self._state_lock:
                            self._last_error = error_message
                        LOGGER.exception(
                            "No fue posible actualizar la luz Hue %s",
                            light_id,
                        )
        except Exception as error:
            with self._state_lock:
                self._last_error = str(error)
            LOGGER.exception("El motor de sinestesia se detuvo por un error")
        finally:
            try:
                self._listener.stop()
            except Exception as error:
                with self._state_lock:
                    self._last_error = str(error)
                LOGGER.exception("No fue posible cerrar el dispositivo de audio")
