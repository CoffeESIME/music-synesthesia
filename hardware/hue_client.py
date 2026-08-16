"""Cliente de hardware para bombillas Philips Hue mediante la API v2."""

import os

import requests
import urllib3

from core.color_math import rgb_to_xy
from core.config import BRIDGE_IP, HUE_APPLICATION_KEY


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HueController:
    """Adapta colores RGB a comandos para una bombilla Philips Hue."""

    def __init__(
        self,
        bridge_ip: str = BRIDGE_IP,
        application_key: str = HUE_APPLICATION_KEY,
        timeout_seconds: float = 2.0,
    ) -> None:
        if not bridge_ip:
            raise ValueError("BRIDGE_IP no esta configurado")
        if not application_key:
            raise ValueError("HUE_APPLICATION_KEY no esta configurado")
        if timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds debe ser mayor que cero")

        self._base_url: str = f"https://{bridge_ip}/clip/v2/resource/light"
        self._timeout_seconds: float = timeout_seconds
        self._session: requests.Session = requests.Session()
        self._session.verify = False
        self._session.headers.update(
            {
                "hue-application-key": application_key,
                "Content-Type": "application/json",
            }
        )

    def set_color(
        self,
        light_id: str,
        rgb: tuple[int, int, int],
        transition_ms: int = 400,
    ) -> requests.Response:
        """Enciende una luz y aplica un color RGB con una transicion en ms."""
        if not light_id.strip():
            raise ValueError("light_id no puede estar vacio")
        if transition_ms < 0:
            raise ValueError("transition_ms no puede ser negativo")

        x, y = rgb_to_xy(*rgb)
        payload: dict[str, object] = {
            "on": {"on": True},
            "color": {"xy": {"x": x, "y": y}},
            "dynamics": {"duration": transition_ms},
        }
        response: requests.Response = self._session.put(
            f"{self._base_url}/{light_id}",
            json=payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response


if __name__ == "__main__":
    test_light_id: str = (
        os.getenv("HUE_TEST_LIGHT_ID", "").strip()
        or os.getenv("FOCO_2", "").strip()
    )
    if not test_light_id:
        raise SystemExit("Configura HUE_TEST_LIGHT_ID para ejecutar la prueba")

    controller = HueController()
    controller.set_color(test_light_id, (255, 0, 0))
    print("Comando rojo enviado correctamente a la bombilla de prueba")
