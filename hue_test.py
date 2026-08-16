import requests
import urllib3
import time
import random

# --- TUS DATOS ---
BRIDGE_IP = "192.168.50.212"  # Reemplaza con tu IP
HUE_KEY = "pX0gGk3dqHABNNH0yB5E9JwXCVNTlMHEGBaBz4gv"


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FOCO_2 = "d695f1ab-7a7b-404d-8b57-ba73f08d24d7"
FOCO_3 = "8c2801b0-fb0b-4ead-bba9-23f061c22a3c"
FOCOS = [FOCO_2, FOCO_3]

# Diccionario de colores en formato CIE xy
COLORES = {
    'rojo':     {'x': 0.7006, 'y': 0.2993},
    'verde':    {'x': 0.1700, 'y': 0.7000},
    'azul':     {'x': 0.1532, 'y': 0.0475},
    'amarillo': {'x': 0.4325, 'y': 0.5007},
    'blanco':   {'x': 0.3227, 'y': 0.3290},
    'rosa':     {'x': 0.4149, 'y': 0.1776}
}

def enviar_comando(foco_id, x, y, brillo=100.0, transicion_ms=400):
    """Envía el JSON a la API v2 de Hue"""
    url = f"https://{BRIDGE_IP}/clip/v2/resource/light/{foco_id}"
    headers = {"hue-application-key": HUE_KEY}
    
    payload = {
        "on": {"on": True},
        "dimming": {"brightness": brillo},
        "color": {"xy": {"x": x, "y": y}},
        "dynamics": {"duration": transicion_ms} # Tiempo de transición en milisegundos
    }
    requests.put(url, headers=headers, json=payload, verify=False)

# ==========================================
# SECUENCIAS AVANZADAS (LAS PALABRAS)
# ==========================================

def secuencia_policia():
    """Efecto estroboscópico de patrulla (Rojo y Azul)"""
    print(">> Iniciando secuencia POLICIA (Presiona Ctrl+C para detener)")
    try:
        for _ in range(10): # Parpadea 10 veces
            enviar_comando(FOCO_2, **COLORES['rojo'], brillo=100, transicion_ms=0)
            enviar_comando(FOCO_3, **COLORES['azul'], brillo=100, transicion_ms=0)
            time.sleep(0.3)
            
            enviar_comando(FOCO_2, **COLORES['azul'], brillo=100, transicion_ms=0)
            enviar_comando(FOCO_3, **COLORES['rojo'], brillo=100, transicion_ms=0)
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass # Permite salir del loop con Ctrl+C sin romper el programa

def secuencia_relax():
    """Transiciones extremadamente lentas para meditar/relajarse"""
    print(">> Iniciando secuencia RELAX")
    # Transición de 5 segundos hacia colores cálidos
    enviar_comando(FOCO_2, **COLORES['rosa'], brillo=30, transicion_ms=5000)
    enviar_comando(FOCO_3, **COLORES['azul'], brillo=30, transicion_ms=5000)
    time.sleep(5)
    enviar_comando(FOCO_2, **COLORES['azul'], brillo=30, transicion_ms=5000)
    enviar_comando(FOCO_3, **COLORES['rosa'], brillo=30, transicion_ms=5000)

def secuencia_fiesta():
    """Genera colores aleatorios rápidos"""
    print(">> Iniciando secuencia FIESTA")
    for _ in range(15):
        for foco in FOCOS:
            rx = random.uniform(0.1, 0.7)
            ry = random.uniform(0.1, 0.7)
            enviar_comando(foco, x=rx, y=ry, brillo=100, transicion_ms=200)
        time.sleep(0.3)

# ==========================================
# BUCLE PRINCIPAL (EL CENTRO DE COMANDOS)
# ==========================================

def panel_control():
    print("\n" + "="*40)
    print("🤖 PANEL DE DEMOSTRACIÓN HUE")
    print("="*40)
    print("Letras/Números simples:")
    print("  R = Rojo  |  G = Verde |  B = Azul")
    print("  Y = Amarillo | W = Blanco")
    print("  1 = Brillo bajo | 2 = Brillo Alto")
    print("\nPalabras (Secuencias):")
    print("  'policia' -> Efecto patrulla")
    print("  'relax'   -> Transición suave")
    print("  'fiesta'  -> Colores aleatorios")
    print("  'salir'   -> Cierra el programa")
    print("="*40)

    brillo_actual = 100.0

    while True:
        comando = input("\nIngresa comando > ").strip().lower()

        if comando == 'salir':
            print("Apagando luces y saliendo...")
            for foco in FOCOS:
                requests.put(f"https://{BRIDGE_IP}/clip/v2/resource/light/{foco}", 
                             headers={"hue-application-key": HUE_KEY}, 
                             json={"on": {"on": False}}, verify=False)
            break

        # --- MANEJO DE LETRAS ---
        elif comando == 'r':
            for f in FOCOS: enviar_comando(f, **COLORES['rojo'], brillo=brillo_actual)
        elif comando == 'g':
            for f in FOCOS: enviar_comando(f, **COLORES['verde'], brillo=brillo_actual)
        elif comando == 'b':
            for f in FOCOS: enviar_comando(f, **COLORES['azul'], brillo=brillo_actual)
        elif comando == 'y':
            for f in FOCOS: enviar_comando(f, **COLORES['amarillo'], brillo=brillo_actual)
        elif comando == 'w':
            for f in FOCOS: enviar_comando(f, **COLORES['blanco'], brillo=brillo_actual)
            
        # --- MANEJO DE BRILLO ---
        elif comando == '1':
            print("Brillo al 20%")
            brillo_actual = 20.0
            # Solo actualizamos el brillo sin cambiar el color
            for f in FOCOS: 
                url = f"https://{BRIDGE_IP}/clip/v2/resource/light/{f}"
                requests.put(url, headers={"hue-application-key": HUE_KEY}, json={"dimming": {"brightness": brillo_actual}}, verify=False)
        elif comando == '2':
            print("Brillo al 100%")
            brillo_actual = 100.0
            for f in FOCOS: 
                url = f"https://{BRIDGE_IP}/clip/v2/resource/light/{f}"
                requests.put(url, headers={"hue-application-key": HUE_KEY}, json={"dimming": {"brightness": brillo_actual}}, verify=False)

        # --- MANEJO DE PALABRAS ---
        elif comando == 'policia':
            secuencia_policia()
        elif comando == 'relax':
            secuencia_relax()
        elif comando == 'fiesta':
            secuencia_fiesta()
        else:
            print("Comando no reconocido. Intenta con 'R', 'B', 'policia', etc.")

if __name__ == "__main__":
    panel_control()