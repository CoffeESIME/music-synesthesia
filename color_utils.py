def rgb_to_xy(r: int, g: int, b: int) -> tuple[float, float]:
    """
    Convierte valores RGB (0-255) al espacio de color CIE xy utilizado por Philips Hue.
    """
    # Normalizar valores a 0.0 - 1.0
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    # Gamma correction
    def apply_gamma(v):
        return ((v + 0.055) / (1.0 + 0.055)) ** 2.4 if v > 0.04045 else (v / 12.92)

    r_gamma = apply_gamma(r_norm)
    g_gamma = apply_gamma(g_norm)
    b_gamma = apply_gamma(b_norm)

    # Convertir a XYZ (Matriz D65)
    x = r_gamma * 0.664511 + g_gamma * 0.154324 + b_gamma * 0.162028
    y = r_gamma * 0.283881 + g_gamma * 0.668433 + b_gamma * 0.047685
    z = r_gamma * 0.000088 + g_gamma * 0.072310 + b_gamma * 0.986039

    # Calcular xy
    sum_xyz = x + y + z
    
    if sum_xyz == 0:
        return 0.0, 0.0
    
    cx = x / sum_xyz
    cy = y / sum_xyz

    # Redondear a 4 decimales
    return round(cx, 4), round(cy, 4)
