"""Aplicacion FastAPI y transporte en tiempo real de Proyecto Sinestesia."""

from __future__ import annotations

import asyncio
import os
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
from core.synesthesia import ALL_PROFILES
from engine.synesthesia_engine import ColorEvent, SynesthesiaEngine
from hardware.hue_client import HueController


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


class NoteTimelineEntry(BaseModel):
    """Nota dominante detectada en un instante de la pista."""

    time: float
    note: str


class AudioUploadResponse(BaseModel):
    """URL reproducible y linea de tiempo pura de notas."""

    audio_url: str
    timeline: list[NoteTimelineEntry]


class LightListResponse(BaseModel):
    """IDs de luces que puede controlar el frontend."""

    light_ids: list[str]


class SetLightCommand(BaseModel):
    """Comando RGB validado para una luz Hue concreta."""

    light_id: str = Field(min_length=1)
    r: int = Field(ge=0, le=255)
    g: int = Field(ge=0, le=255)
    b: int = Field(ge=0, le=255)
    transition: int = Field(default=100, ge=0, le=60_000)


class SetLightResponse(BaseModel):
    """Confirmacion del color enviado al adaptador Hue."""

    light_id: str
    rgb: tuple[int, int, int]
    transition: int


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


def _get_engine(app: FastAPI) -> SynesthesiaEngine:
    """Obtiene el motor inicializado durante el lifespan de la aplicacion."""
    engine: object | None = getattr(app.state, "engine", None)
    if not isinstance(engine, SynesthesiaEngine):
        raise HTTPException(status_code=503, detail="El motor no esta disponible")
    return engine


def _get_hue_controller(app: FastAPI) -> HueController:
    """Obtiene el adaptador Hue inicializado durante el lifespan."""
    controller: object | None = getattr(app.state, "hue_controller", None)
    if not isinstance(controller, HueController):
        raise HTTPException(status_code=503, detail="El controlador Hue no esta disponible")
    return controller


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
    app.state.hue_controller = hue_controller
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


@app.get("/api/client-config")
async def get_client_config() -> dict[str, int]:
    """Puerto HTTPS público para solicitar el micrófono del navegador en LAN."""
    return {"https_port": int(os.getenv("SINESTESIA_HTTPS_PORT", "18744"))}


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


@app.get("/api/profiles")
async def get_profiles() -> dict[str, dict[str, list[int]]]:
    """Expone los perfiles RGB para el mapeo dinamico en el frontend."""
    return {
        profile_name: {
            note: list(rgb)
            for note, rgb in profile.items()
        }
        for profile_name, profile in ALL_PROFILES.items()
    }


@app.get("/api/lights", response_model=LightListResponse)
async def get_lights() -> LightListResponse:
    """Expone los IDs configurados que puede actualizar el reproductor."""
    return LightListResponse(light_ids=list(HUE_LIGHT_IDS))


@app.post("/api/profile/{name}", response_model=ProfileResponse)
async def change_profile(name: str, request: Request) -> ProfileResponse:
    """Cambia el perfil sinestetico de forma segura mientras el motor corre."""
    engine: SynesthesiaEngine = _get_engine(cast(FastAPI, request.app))
    try:
        engine.set_profile(name)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ProfileResponse(profile=engine.active_profile)


@app.post("/api/set_light", response_model=SetLightResponse)
async def set_light(
    command: SetLightCommand,
    request: Request,
) -> SetLightResponse:
    """Envia un RGB a una luz Hue fuera del Event Loop de FastAPI."""
    light_id: str = command.light_id.strip()
    if light_id not in HUE_LIGHT_IDS:
        raise HTTPException(status_code=404, detail="La luz solicitada no esta configurada")

    controller: HueController = _get_hue_controller(cast(FastAPI, request.app))
    rgb: tuple[int, int, int] = (command.r, command.g, command.b)
    try:
        await asyncio.to_thread(
            controller.set_color,
            light_id,
            rgb,
            command.transition,
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible actualizar la luz Hue: {error}",
        ) from error

    return SetLightResponse(
        light_id=light_id,
        rgb=rgb,
        transition=command.transition,
    )


@app.post("/api/upload", response_model=AudioUploadResponse)
async def upload_audio(
    file: UploadFile = File(...),
) -> AudioUploadResponse:
    """Guarda una pista y extrae su timeline de notas una sola vez."""
    from audio.file_analyzer import analyze_audio_file

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
    try:
        await asyncio.to_thread(_save_audio_upload, file, destination)
        timeline: list[dict[str, float | str]] = await asyncio.to_thread(
            analyze_audio_file,
            str(destination),
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
        timeline=[
            NoteTimelineEntry(
                time=float(cue["time"]),
                note=str(cue["note"]),
            )
            for cue in timeline
        ],
    )


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
