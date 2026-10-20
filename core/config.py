"""Configuracion de la app web y la integracion local opcional con Hue."""

import os

from dotenv import load_dotenv


load_dotenv()


def _load_bool(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default).strip().lower()
    if value not in {"true", "false", "1", "0"}:
        raise ValueError(f"{name} debe ser true, false, 1 o 0")
    return value in {"true", "1"}


HUE_ENABLED: bool = _load_bool("HUE_ENABLED")

BRIDGE_IP: str = os.getenv("BRIDGE_IP", "").strip()
HUE_APPLICATION_KEY: str = os.getenv("HUE_APPLICATION_KEY", "").strip()


def _load_light_ids() -> tuple[str, ...]:
    """Carga IDs separados por coma o usa las variables heredadas del proyecto."""
    configured_ids: str = os.getenv("HUE_LIGHT_IDS", "")
    light_ids: tuple[str, ...] = tuple(
        light_id.strip() for light_id in configured_ids.split(",") if light_id.strip()
    )
    if light_ids:
        return light_ids

    legacy_ids: tuple[str, ...] = (
        os.getenv("FOCO_2", "").strip(),
        os.getenv("FOCO_3", "").strip(),
    )
    return tuple(light_id for light_id in legacy_ids if light_id)


HUE_LIGHT_IDS: tuple[str, ...] = _load_light_ids()
