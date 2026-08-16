"""Aplicacion FastAPI y transporte en tiempo real de Proyecto Sinestesia."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.config import HUE_LIGHT_IDS
from core.synesthesia import PERFILES
from engine.synesthesia_engine import ColorEvent, SynesthesiaEngine


PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
STATIC_DIR: Path = PROJECT_ROOT / "static"
TEMP_DIR: Path = PROJECT_ROOT / "temp"
MAX_AUDIO_BYTES: int = 250 * 1024 * 1024
ALLOWED_AUDIO_SUFFIXES: frozenset[str] = frozenset({".wav", ".mp3"})


class EngineStatus(BaseModel):
    """Estado publico del motor de escucha."""

    running: bool
    profile: str
    last_error: str | None


class ProfileResponse(BaseModel):
    """Confirmacion del perfil activo."""

    profile: str


class LightingCueResponse(BaseModel):
    """Cue temporal producido por el analizador de pista."""

    time_sec: float
    color_hex: str
    note: str


class AudioUploadResponse(BaseModel):
    """Resultado de carga junto con la URL reproducible del audio."""

    audio_url: str
    lighting_map: list[LightingCueResponse]


class TrackColorCommand(BaseModel):
    """Color que debe aplicarse durante la reproduccion de una pista."""

    note: str = Field(min_length=1, max_length=2)
    color_hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    transition_ms: int = Field(default=100, ge=0, le=60_000)


class TrackColorResponse(BaseModel):
    """Confirmacion del ultimo cue aplicado."""

    note: str
    color_hex: str


class AudioFileTooLargeError(ValueError):
    """Indica que un archivo supera el limite permitido."""


def _save_audio_upload(upload: UploadFile, destination: Path) -> None:
    """Copia un UploadFile a disco con un limite estricto de bytes."""
    total_bytes: int = 0
    upload.file.seek(0)
    with destination.open("wb") as output:
        while chunk := upload.file.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > MAX_AUDIO_BYTES:
                raise AudioFileTooLargeError(
                    "El archivo supera el limite permitido de 250 MB"
                )
            output.write(chunk)


def _hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    """Convierte un hexadecimal validado a una tupla RGB."""
    return (
        int(color_hex[1:3], 16),
        int(color_hex[3:5], 16),
        int(color_hex[5:7], 16),
    )


def _get_engine(app: FastAPI) -> SynesthesiaEngine:
    """Obtiene el motor inicializado durante el lifespan de la aplicacion."""
    engine: object | None = getattr(app.state, "engine", None)
    if not isinstance(engine, SynesthesiaEngine):
        raise HTTPException(status_code=503, detail="El motor no esta disponible")
    return engine


def _engine_status(engine: SynesthesiaEngine) -> EngineStatus:
    """Construye la respuesta de estado comun para los endpoints REST."""
    return EngineStatus(
        running=engine.is_running,
        profile=engine.active_profile,
        last_error=engine.last_error,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Crea los adaptadores al arrancar y libera el microfono al cerrar."""
    if not HUE_LIGHT_IDS:
        raise RuntimeError("Configura HUE_LIGHT_IDS en .env con al menos una luz")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Imports diferidos: importar la API no abre ni requiere el dispositivo de audio.
    from audio.pitch_detector import AudioListener
    from hardware.hue_client import HueController

    listener = AudioListener()
    hue_controller = HueController()
    engine = SynesthesiaEngine(
        listener=listener,
        hue_controller=hue_controller,
        light_ids=HUE_LIGHT_IDS,
        profile_name="scriabin",
        transition_ms=100,
    )
    app.state.engine = engine
    try:
        yield
    finally:
        await asyncio.to_thread(engine.stop)


app = FastAPI(
    title="Proyecto Sinestesia",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    """Sirve la pagina principal almacenada en static/."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status", response_model=EngineStatus)
async def get_status(request: Request) -> EngineStatus:
    """Devuelve el estado actual del motor."""
    engine: SynesthesiaEngine = _get_engine(cast(FastAPI, request.app))
    return _engine_status(engine)


@app.post("/api/listener/start", response_model=EngineStatus)
async def start_listener(request: Request) -> EngineStatus:
    """Inicia la captura en el hilo daemon sin bloquear FastAPI."""
    engine: SynesthesiaEngine = _get_engine(cast(FastAPI, request.app))
    engine.start()
    return _engine_status(engine)


@app.post("/api/listener/stop", response_model=EngineStatus)
async def stop_listener(request: Request) -> EngineStatus:
    """Detiene el worker fuera del Event Loop y devuelve su estado final."""
    engine: SynesthesiaEngine = _get_engine(cast(FastAPI, request.app))
    stopped: bool = await asyncio.to_thread(engine.stop)
    if not stopped:
        raise HTTPException(status_code=503, detail="El motor no se detuvo a tiempo")
    return _engine_status(engine)


@app.post("/api/profile/{name}", response_model=ProfileResponse)
async def change_profile(name: str, request: Request) -> ProfileResponse:
    """Cambia el perfil sinestetico de forma segura mientras el motor corre."""
    engine: SynesthesiaEngine = _get_engine(cast(FastAPI, request.app))
    try:
        engine.set_profile(name)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ProfileResponse(profile=engine.active_profile)


@app.post("/upload_audio", response_model=AudioUploadResponse)
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
) -> AudioUploadResponse:
    """Guarda y analiza una pista WAV o MP3 fuera del Event Loop."""
    from audio.file_analyzer import analyze_audio_file

    engine: SynesthesiaEngine = _get_engine(cast(FastAPI, request.app))
    original_name: str = file.filename or ""
    suffix: str = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        await file.close()
        raise HTTPException(
            status_code=415,
            detail="El archivo debe tener extension .wav o .mp3",
        )

    stored_name: str = f"{uuid4().hex}{suffix}"
    destination: Path = TEMP_DIR / stored_name
    profile: dict[str, list[int]] = {
        note: list(rgb)
        for note, rgb in PERFILES[engine.active_profile].items()
    }
    try:
        await asyncio.to_thread(_save_audio_upload, file, destination)
        lighting_map: list[dict[str, float | str]] = await asyncio.to_thread(
            analyze_audio_file,
            str(destination),
            profile,
        )
    except AudioFileTooLargeError as error:
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        raise HTTPException(status_code=413, detail=str(error)) from error
    except Exception as error:
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=f"No fue posible analizar el audio: {error}",
        ) from error
    finally:
        await file.close()

    return AudioUploadResponse(
        audio_url=f"/temp/{stored_name}",
        lighting_map=[
            LightingCueResponse(
                time_sec=float(cue["time_sec"]),
                color_hex=str(cue["color_hex"]),
                note=str(cue["note"]),
            )
            for cue in lighting_map
        ],
    )


@app.post("/api/track/color", response_model=TrackColorResponse)
async def apply_track_color(
    command: TrackColorCommand,
    request: Request,
) -> TrackColorResponse:
    """Aplica un cue de pista sin bloquear el Event Loop de FastAPI."""
    engine: SynesthesiaEngine = _get_engine(cast(FastAPI, request.app))
    if engine.is_running:
        raise HTTPException(
            status_code=409,
            detail="Deten la escucha en vivo antes de reproducir una pista",
        )

    normalized_hex: str = command.color_hex.upper()
    try:
        await asyncio.to_thread(
            engine.apply_track_color,
            command.note,
            _hex_to_rgb(normalized_hex),
            command.transition_ms,
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible actualizar las luces Hue: {error}",
        ) from error
    return TrackColorResponse(note=command.note, color_hex=normalized_hex)


async def _wait_for_disconnect(websocket: WebSocket) -> None:
    """Espera mensajes para detectar inmediatamente el cierre del cliente."""
    while True:
        message: dict[str, object] = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            return


async def _stream_colors(websocket: WebSocket, engine: SynesthesiaEngine) -> None:
    """Publica cada nuevo ColorEvent sin bloquear el Event Loop."""
    previous_event: ColorEvent | None = None
    while True:
        event: ColorEvent | None = engine.last_event
        if event is not None and event is not previous_event:
            await websocket.send_json(
                {
                    "nota": event.note,
                    "color": event.hex_color,
                }
            )
            previous_event = event
        await asyncio.sleep(0.02)


@app.websocket("/ws/color_stream")
async def color_stream(websocket: WebSocket) -> None:
    """Mantiene un stream independiente de nota y color para cada cliente."""
    engine: SynesthesiaEngine = _get_engine(cast(FastAPI, websocket.app))
    await websocket.accept()
    disconnect_task: asyncio.Task[None] = asyncio.create_task(
        _wait_for_disconnect(websocket)
    )
    stream_task: asyncio.Task[None] = asyncio.create_task(
        _stream_colors(websocket, engine)
    )
    tasks: set[asyncio.Task[None]] = {disconnect_task, stream_task}

    try:
        completed, _ = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in completed:
            task.result()
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/temp", StaticFiles(directory=TEMP_DIR, check_dir=False), name="temp")
