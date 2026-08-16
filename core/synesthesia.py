"""Perfiles de correspondencia entre notas cromaticas y colores RGB."""


# Extension cromatica del circulo de colores propuesto por Isaac Newton.
PERFIL_NEWTON: dict[str, list[int]] = {
    "C": [255, 0, 0],
    "C#": [255, 64, 0],
    "D": [255, 127, 0],
    "D#": [255, 191, 0],
    "E": [255, 255, 0],
    "F": [0, 255, 0],
    "F#": [0, 255, 127],
    "G": [0, 0, 255],
    "G#": [75, 0, 130],
    "A": [139, 0, 255],
    "A#": [200, 0, 255],
    "B": [255, 0, 255],
}

# Aproximacion RGB de la tabla de correspondencias de Alexander Scriabin.
PERFIL_SCRIABIN: dict[str, list[int]] = {
    "C": [255, 0, 0],
    "C#": [148, 0, 211],
    "D": [255, 255, 0],
    "D#": [192, 192, 192],
    "E": [135, 206, 235],
    "F": [139, 0, 0],
    "F#": [0, 0, 255],
    "G": [255, 165, 0],
    "G#": [128, 0, 128],
    "A": [0, 255, 0],
    "A#": [255, 105, 180],
    "B": [0, 191, 255],
}

PERFILES: dict[str, dict[str, list[int]]] = {
    "newton": PERFIL_NEWTON,
    "scriabin": PERFIL_SCRIABIN,
}
