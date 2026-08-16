"""Aplicacion FastAPI y transporte en tiempo real de Proyecto Sinestesia."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import HUE_LIGHT_IDS
from engine.synesthesia_engine import ColorEvent, SynesthesiaEngine


PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
STATIC_DIR: Path = PROJECT_ROOT / "static"


class EngineStatus(BaseModel):
    """Estado publico del motor de escucha."""

    running: bool
    profile: str
    last_error: str | None


class ProfileResponse(BaseModel):
    """Confirmacion del perfil activo."""

    profile: str


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
