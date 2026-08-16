"""Conversiones entre espacios de color usadas por Philips Hue."""


def _linearize(channel: float) -> float:
    """Convierte un canal sRGB normalizado a su valor RGB lineal."""
    if channel > 0.04045:
        return ((channel + 0.055) / 1.055) ** 2.4
    return channel / 12.92


def rgb_to_xy(r: int, g: int, b: int) -> tuple[float, float]:
    """Convierte un color RGB de 8 bits a coordenadas CIE 1931 xy de Hue."""
    channels: tuple[int, int, int] = (r, g, b)
    if any(channel < 0 or channel > 255 for channel in channels):
        raise ValueError("Los canales RGB deben estar entre 0 y 255")

    red: float = _linearize(r / 255.0)
    green: float = _linearize(g / 255.0)
    blue: float = _linearize(b / 255.0)

    # Matriz Wide RGB D65 recomendada para la conversion de color de Hue.
    x_value: float = red * 0.664511 + green * 0.154324 + blue * 0.162028
    y_value: float = red * 0.283881 + green * 0.668433 + blue * 0.047685
    z_value: float = red * 0.000088 + green * 0.072310 + blue * 0.986039
    total: float = x_value + y_value + z_value

    if total == 0.0:
        return (0.0, 0.0)

    return (x_value / total, y_value / total)
