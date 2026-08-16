import time
import threading
import requests
import urllib3
import os
from dotenv import load_dotenv
from color_utils import rgb_to_xy

# Silenciar warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

BRIDGE_IP = os.getenv("BRIDGE_IP")
HUE_KEY = os.getenv("HUE_APPLICATION_KEY")
FOCO_1 = os.getenv("FOCO_2")  # Mapeado a los IDs del script original
FOCO_2 = os.getenv("FOCO_3")
FOCOS = [FOCO_1, FOCO_2]

# Estado global
current_mode = None
current_colors = []
state_changed_event = threading.Event()
lock = threading.Lock()

def send_command(foco_id, r, g, b, duration_ms):
    if not foco_id:
        return
    x, y = rgb_to_xy(r, g, b)
    url = f"https://{BRIDGE_IP}/clip/v2/resource/light/{foco_id}"
    headers = {"hue-application-key": HUE_KEY}
    payload = {
        "on": {"on": True},
        "dimming": {"brightness": 100},
        "color": {"xy": {"x": x, "y": y}},
        "dynamics": {"duration": duration_ms}
    }
    try:
        requests.put(url, headers=headers, json=payload, verify=False, timeout=2)
    except Exception as e:
        print(f"Error sending command to Hue: {e}")

def modo_respiracion(colors):
    # Nivel 1: Cicla entre 2 colores con duration: 3000
    c1, c2 = colors[0], colors[1]
    while not state_changed_event.is_set():
        for foco in FOCOS:
            send_command(foco, *c1, 3000)
        
        # Esperar 3 segundos de manera interrumpible
        if state_changed_event.wait(3.0):
            break
            
        for foco in FOCOS:
            send_command(foco, *c2, 3000)
            
        if state_changed_event.wait(3.0):
            break

def modo_escena(colors):
    # Nivel 2: Foco A (Fondo), Foco B (Acento). Estáticos con duration: 1000
    fondo = colors[0]
    acento = colors[1]
    
    if len(FOCOS) >= 2:
        send_command(FOCOS[0], *fondo, 1000)
        send_command(FOCOS[1], *acento, 1000)
    elif len(FOCOS) == 1:
        send_command(FOCOS[0], *fondo, 1000)
        
    # Mantener el estado hasta que cambie
    state_changed_event.wait()

def modo_frenetico(colors):
    # Nivel 3: Bucle rápido ciclando la paleta de colores. duration: 0, sleep: 0.15
    idx = 0
    num_colors = len(colors)
    while not state_changed_event.is_set():
        if num_colors > 0:
            c = colors[idx % num_colors]
            for foco in FOCOS:
                send_command(foco, *c, 0)
            idx += 1
            
        if state_changed_event.wait(0.15):
            break

def hue_worker():
    global current_mode, current_colors
    while True:
        with lock:
            mode = current_mode
            colors = current_colors
            state_changed_event.clear()
            
        if mode == "respiracion" and len(colors) >= 2:
            modo_respiracion(colors)
        elif mode == "escena" and len(colors) >= 2:
            modo_escena(colors)
        elif mode == "frenetico" and len(colors) > 0:
            modo_frenetico(colors)
        else:
            # Esperar a que se asigne un estado
            state_changed_event.wait()

def set_state(level, colors):
    global current_mode, current_colors
    with lock:
        if level == 1:
            current_mode = "respiracion"
        elif level == 2:
            current_mode = "escena"
        elif level == 3:
            current_mode = "frenetico"
        
        current_colors = colors
        state_changed_event.set()

def start_hue_controller():
    t = threading.Thread(target=hue_worker, daemon=True)
    t.start()
