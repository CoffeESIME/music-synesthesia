import math
from colorthief import ColorThief

def color_distance(c1, c2):
    return math.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2 + (c1[2]-c2[2])**2)

def analyze_image(image_path: str):
    """
    Analiza una imagen y extrae una paleta de colores.
    Calcula la complejidad en base a la varianza de color.
    
    Niveles:
    1 (Baja): Colores muy similares. Devuelve 2.
    2 (Media): Varianza media. Devuelve 2 (Fondo y Acento).
    3 (Alta): Varianza alta. Devuelve 5-6 colores vibrantes.
    """
    color_thief = ColorThief(image_path)
    # Extraer paleta de hasta 6 colores
    try:
        palette = color_thief.get_palette(color_count=6)
    except Exception as e:
        # Fallback en caso de error
        return {
            "level": 1,
            "complexity": "Baja",
            "colors": [(255, 255, 255), (200, 200, 200)]
        }
    
    if not palette:
        return {
            "level": 1,
            "complexity": "Baja",
            "colors": [(255, 255, 255), (200, 200, 200)]
        }
    
    # Calcular distancia media entre los colores de la paleta
    distances = []
    for i in range(len(palette)):
        for j in range(i+1, len(palette)):
            distances.append(color_distance(palette[i], palette[j]))
            
    avg_distance = sum(distances) / len(distances) if distances else 0

    if avg_distance < 60:
        level = 1
        complexity = "Baja"
        colors = palette[:2] if len(palette) >= 2 else [palette[0], palette[0]]
    elif avg_distance < 120:
        level = 2
        complexity = "Media"
        # Encontrar el color más contrastante al dominante
        dominant = palette[0]
        most_contrast = palette[1]
        max_dist = 0
        for color in palette[1:]:
            dist = color_distance(dominant, color)
            if dist > max_dist:
                max_dist = dist
                most_contrast = color
        colors = [dominant, most_contrast]
    else:
        level = 3
        complexity = "Alta"
        colors = palette[:6]

    return {
        "level": level,
        "complexity": complexity,
        "colors": colors
    }
